from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Operator, SKU, LabelVersion, ShipmentBatch

class WarehouseLogicTest(TestCase):
    def setUp(self):
        """测试数据初始化"""
        self.client = APIClient()
        
        # 1. 创建三个角色：操作员(创建者)、审核员A、审核员B
        self.operator = Operator.objects.create(username="op_user", full_name="Operator 1")
        self.reviewer1 = Operator.objects.create(username="mgr_1", full_name="Manager 1")
        self.reviewer2 = Operator.objects.create(username="mgr_2", full_name="Manager 2")
        
        # 2. 创建基础 SKU
        self.sku = SKU.objects.create(sku_code="SKU-001", product_name="Test Product")

    # --- 测试核心 A: 标签版本控制与哈希 ---
    def test_label_version_increment_and_hashing(self):
        print("\n正在测试: 标签版本自增与哈希生成...")
        
        # 1. 创建 V0 版本
        v0 = LabelVersion.create_version(self.sku, "FNSKU_A", "UPC_A", "system")
        self.assertEqual(v0.version_number, 0)
        self.assertTrue(len(v0.checksum) == 64) # 验证生成了 SHA256
        print(f"  V0 Checksum: {v0.checksum} (验证通过)")

        # 2. 创建 V1 版本 (模拟修改标签)
        v1 = LabelVersion.create_version(self.sku, "FNSKU_B", "UPC_A", "system")
        self.assertEqual(v1.version_number, 1)
        self.assertNotEqual(v0.checksum, v1.checksum) # 哈希值必须变化
        print(f"  V1 Checksum: {v1.checksum} (验证通过 - 哈希已变更)")

        # 3. 验证历史数据不可变性 (查询数据库确认 V0 还是 V0)
        v0_check = LabelVersion.objects.get(id=v0.id)
        self.assertEqual(v0_check.fnsku, "FNSKU_A")
        print("  历史版本回溯验证通过")

    # --- 测试核心 B: 双重审核流程 ---
    def test_dual_review_workflow(self):
        print("\n正在测试: 双重审核流程与权限隔离...")
        
        # 准备数据：创建一个标签和一个批次
        label = LabelVersion.create_version(self.sku, "FN_TEST", "UPC_TEST", "system")
        batch = ShipmentBatch.objects.create(
            batch_code="BATCH-2023001",
            label=label,
            quantity=100,
            created_by=self.operator
        )
        
        url = f'/api/batches/{batch.id}/review/' # 假设这是我们在 router 中注册的路径

        # 1. 测试：创建者试图自己审核 (应该失败)
        response = self.client.post(url, {
            "reviewer_role": "1",
            "approved": True,
            "operator_id": self.operator.id # 模拟当前登录用户
        })
        self.assertEqual(response.status_code, 403)
        print("  反自审机制: 拦截成功 (创建者不能审核)")

        # 2. 测试：审核员 1 进行第一次审核
        response = self.client.post(url, {
            "reviewer_role": "1",
            "approved": True,
            "operator_id": self.reviewer1.id
        })
        self.assertEqual(response.status_code, 200)
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'reviewing') # 只有一人审核，状态应为 reviewing
        print("  第一层审核: 成功 (状态流转为 reviewing)")

        # 3. 测试：审核员 1 试图再次充当审核员 2 (应该失败)
        response = self.client.post(url, {
            "reviewer_role": "2", # 试图占 2 号位
            "approved": True,
            "operator_id": self.reviewer1.id # 还是同一个人
        })
        self.assertEqual(response.status_code, 403)
        print("  互斥机制: 拦截成功 (同一人不能既是一审又是二审)")

        # 4. 测试：审核员 2 进行第二次审核 (完成流程)
        response = self.client.post(url, {
            "reviewer_role": "2",
            "approved": True,
            "operator_id": self.reviewer2.id
        })
        self.assertEqual(response.status_code, 200)
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'approved') # 两人都通过，状态应为 approved
        print("  第二层审核: 成功 (状态流转为 approved)")