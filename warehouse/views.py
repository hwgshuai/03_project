from django.shortcuts import render

# Create your views here.
# warehouse/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import SKU, LabelVersion, ShipmentBatch, Operator
from .serializers import SKUSerializer, LabelVersionSerializer, ShipmentBatchSerializer

class SKUViewSet(viewsets.ModelViewSet):
    queryset = SKU.objects.all()
    serializer_class = SKUSerializer

class LabelVersionViewSet(viewsets.ModelViewSet):
    queryset = LabelVersion.objects.all()
    serializer_class = LabelVersionSerializer
    
    # 覆写 create 方法：利用 Model 中定义的 create_version 逻辑
    def create(self, request, *args, **kwargs):
        sku_id = request.data.get('sku')
        fnsku = request.data.get('fnsku')
        upc = request.data.get('upc')
        
        # 假设已集成 Auth，从 request.user 获取操作人
        # 这里暂时用 request.data 中的 user 模拟，正式上线请改为 request.user.username
        created_by = request.data.get('created_by', 'system') 

        try:
            sku = SKU.objects.get(id=sku_id)
            new_version = LabelVersion.create_version(
                sku=sku,
                fnsku=fnsku,
                upc=upc,
                created_by=created_by
            )
            serializer = self.get_serializer(new_version)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except SKU.DoesNotExist:
            return Response({"error": "SKU not found"}, status=status.HTTP_404_NOT_FOUND)

class ShipmentBatchViewSet(viewsets.ModelViewSet):
    queryset = ShipmentBatch.objects.all()
    serializer_class = ShipmentBatchSerializer

    def perform_create(self, serializer):
        # 自动关联创建人
        # serializer.save(created_by=self.request.user)
        # 暂时为了测试方便，先不强制 user，实际开发请解开上一行
        serializer.save()

    # --- 核心风控逻辑：审核接口 ---
    
    @action(detail=True, methods=['post'], url_path='review')
    def review_batch(self, request, pk=None):
        """
        前端发送 POST /api/batches/{id}/review/
        Body: { 
            "reviewer_role": "1" or "2", 
            "approved": true, 
            "comment": "OK",
            "operator_id": 1  (实际应从 Token 获取当前登录用户 ID)
        }
        """
        batch = self.get_object()
        data = request.data
        
        operator_id = data.get('operator_id') # 实际项目中应使用 request.user
        role = data.get('reviewer_role') # '1' for Reviewer1, '2' for Reviewer2
        approved = data.get('approved', False)
        comment = data.get('comment', '')

        try:
            operator = Operator.objects.get(id=operator_id)
        except Operator.DoesNotExist:
            return Response({"error": "Operator not found"}, status=400)

        # 1. 校验：审核人不能是创建人 (自审自批风险)
        if batch.created_by and batch.created_by.id == operator.id:
             return Response({"error": "Reviewer cannot be the creator."}, status=403)

        # 2. 校验：Reviewer 1 和 Reviewer 2 不能是同一个人
        if role == '1':
            if batch.reviewer2 and batch.reviewer2.id == operator.id:
                return Response({"error": "Reviewer 1 cannot be the same as Reviewer 2."}, status=403)
            
            batch.reviewer1 = operator
            batch.reviewer1_approved = approved
            batch.reviewer1_comment = comment
            batch.reviewer1_at = timezone.now()
            
        elif role == '2':
            if batch.reviewer1 and batch.reviewer1.id == operator.id:
                return Response({"error": "Reviewer 2 cannot be the same as Reviewer 1."}, status=403)

            batch.reviewer2 = operator
            batch.reviewer2_approved = approved
            batch.reviewer2_comment = comment
            batch.reviewer2_at = timezone.now()
        
        else:
            return Response({"error": "Invalid reviewer role. Use '1' or '2'."}, status=400)

        # 3. 触发状态机更新
        batch.update_status_based_on_reviews()
        batch.save()
        
        return Response(ShipmentBatchSerializer(batch).data)
