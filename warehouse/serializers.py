# warehouse/serializers.py
from rest_framework import serializers
from .models import Operator, SKU, LabelVersion, ShipmentBatch

class OperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operator
        fields = ['id', 'username', 'full_name', 'email']

class SKUSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = '__all__'

class LabelVersionSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    
    class Meta:
        model = LabelVersion
        fields = ['id', 'sku', 'sku_code', 'version_number', 'fnsku', 'upc', 'created_by', 'created_at', 'checksum']
        read_only_fields = ['version_number', 'created_at', 'checksum', 'created_by']

class ShipmentBatchSerializer(serializers.ModelSerializer):
    # 嵌套显示 label 信息，方便前端直接读取版本号和 FNSKU
    label_details = LabelVersionSerializer(source='label', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    reviewer1_name = serializers.CharField(source='reviewer1.username', read_only=True)
    reviewer2_name = serializers.CharField(source='reviewer2.username', read_only=True)

    class Meta:
        model = ShipmentBatch
        fields = [
            'id', 'batch_code', 'label', 'label_details', 'quantity', 'status', 
            'created_at', 'created_by', 'created_by_name',
            'reviewer1', 'reviewer1_name', 'reviewer1_approved', 'reviewer1_comment', 'reviewer1_at',
            'reviewer2', 'reviewer2_name', 'reviewer2_approved', 'reviewer2_comment', 'reviewer2_at'
        ]
        # 核心逻辑：审核字段不应该由前端在"创建"或"普通修改"时直接写入，需要通过专门的审核接口
        read_only_fields = [
            'status', 'created_by', 
            'reviewer1', 'reviewer1_approved', 'reviewer1_comment', 'reviewer1_at',
            'reviewer2', 'reviewer2_approved', 'reviewer2_comment', 'reviewer2_at'
        ]