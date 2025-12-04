# warehouse/models.py
from django.db import models
import hashlib


class Operator(models.Model):
    username = models.CharField(max_length=50, unique=True, verbose_name="Username")
    full_name = models.CharField(max_length=100, blank=True, verbose_name="Full Name")
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

class SKU(models.Model):
    sku_code = models.CharField(max_length=100, unique=True)
    product_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.sku_code

#
#
#
#

class LabelVersion(models.Model):
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    version_number = models.IntegerField()
    fnsku = models.CharField(max_length=100, blank=True)
    upc = models.CharField(max_length=100, blank=True)
    created_by = models.CharField(max_length=50)  # 可改为 ForeignKey(Operator)，但为简化先保留
    created_at = models.DateTimeField(auto_now_add=True)
    checksum = models.CharField(max_length=64, editable=False)

    class Meta:
        unique_together = ('sku', 'version_number')

    def save(self, *args, **kwargs):
        raw = f"{self.fnsku}|{self.upc}"
        self.checksum = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        super().save(*args, **kwargs)

    @classmethod
    def create_version(cls, sku, fnsku, upc, created_by):
        last = cls.objects.filter(sku=sku).order_by('-version_number').first()
        next_ver = (last.version_number + 1) if last else 0
        return cls.objects.create(
            sku=sku,
            version_number=next_ver,
            fnsku=fnsku,
            upc=upc,
            created_by=created_by
        )

    def __str__(self):
        return f"{self.sku.sku_code} - v{self.version_number}"
#
#
#
#

class ShipmentBatch(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewing', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    batch_code = models.CharField(max_length=100, unique=True)
    label = models.ForeignKey(LabelVersion, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Operator, on_delete=models.SET_NULL, null=True, related_name='created_batches')

    # 审核字段
    reviewer1 = models.ForeignKey(
        Operator, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_batches_1', verbose_name="First Reviewer"
    )
    reviewer1_approved = models.BooleanField(default=False)
    reviewer1_comment = models.TextField(blank=True)
    reviewer1_at = models.DateTimeField(null=True, blank=True)

    reviewer2 = models.ForeignKey(
        Operator, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_batches_2', verbose_name="Second Reviewer"
    )
    reviewer2_approved = models.BooleanField(default=False)
    reviewer2_comment = models.TextField(blank=True)
    reviewer2_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.batch_code

    def update_status_based_on_reviews(self):
        
        from django.utils import timezone
        if self.reviewer1_approved and self.reviewer2_approved:
            self.status = 'approved'
        elif self.reviewer1 and not self.reviewer1_approved:
            self.status = 'rejected'
        elif self.reviewer2 and not self.reviewer2_approved:
            self.status = 'rejected'
        else:
            self.status = 'reviewing'
        self.save(update_fields=['status'])

class WarehouseLocation(models.Model):
    """
    仓库库位表
    定义仓库中的物理位置（如：A-01-01），用于精确管理库存位置。
    """
    LOCATION_TYPE_CHOICES = [
        ('receiving', 'Receiving Area'), # 收货区
        ('storage', 'Storage Area'),     # 存储区
        ('picking', 'Picking Area'),     # 拣货区
        ('shipping', 'Shipping Area'),   # 发货区
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name="Location Code")
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='storage')
    is_active = models.BooleanField(default=True)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.code} ({self.location_type})"


class InventoryStock(models.Model):
    """
    实时库存表
    记录当前仓库中，特定库位上、特定标签版本的商品数量。
    核心逻辑：库存不仅仅是 SKU 的库存，而是 'LabelVersion' 的库存，实现风险隔离。
    """
    location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT)
    label_version = models.ForeignKey(LabelVersion, on_delete=models.PROTECT) # 关联到具体的标签版本
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 同一个库位、同一个标签版本只能有一条记录
        unique_together = ('location', 'label_version')

    def __str__(self):
        return f"{self.location.code} - {self.label_version} : {self.quantity}"


class InboundReceipt(models.Model):
    """
    入库单（收货单）
    记录一次完整的入库作业头部信息。
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),         # 草稿
        ('processing', 'Processing'), # 收货中
        ('completed', 'Completed'),   # 已完成
    ]
    
    receipt_no = models.CharField(max_length=100, unique=True)
    reference_no = models.CharField(max_length=100, blank=True, help_text="External PO number") # 外部单号
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    operator = models.ForeignKey(Operator, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.receipt_no


class InboundLineItem(models.Model):
    """
    入库明细
    记录入库单中具体的商品、数量及目标库位。
    """
    receipt = models.ForeignKey(InboundReceipt, related_name='items', on_delete=models.CASCADE)
    # 入库时也必须指定是哪个版本（通常是扫描标签确认版本）
    label_version = models.ForeignKey(LabelVersion, on_delete=models.PROTECT)
    target_location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT)
    quantity_declared = models.PositiveIntegerField(default=0, help_text="Quantity expected") # 申报数量
    quantity_received = models.PositiveIntegerField(default=0, help_text="Actual quantity scanned") # 实收数量
    
    # 新增：入库时的哈希校验记录（可选），用于证明入库时扫描的标签是对的
    scanned_hash = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"{self.receipt.receipt_no} - {self.label_version.sku.sku_code}"


class OutboundExecution(models.Model):
    """
    出库执行任务（拣货单）
    将‘审核通过的批次’ (ShipmentBatch) 转化为具体的‘仓库作业任务’。
    一个 ShipmentBatch 对应一个 Execution，用于记录实际拣货过程。
    """
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),   # 已分配任务
        ('picking', 'Picking'),     # 拣货中
        ('packed', 'Packed'),       # 已打包
        ('shipped', 'Shipped'),     # 已发货（库存扣减终态）
    ]

    # 一对一关联：一个批次对应一次出库执行
    batch = models.OneToOneField(ShipmentBatch, on_delete=models.CASCADE, related_name='execution')
    picker = models.ForeignKey(Operator, on_delete=models.SET_NULL, null=True, verbose_name="Picker")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    
    # 实际发货时间
    shipped_at = models.DateTimeField(null=True, blank=True)
    # 物流单号 (Tracking Number)
    tracking_number = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"EXEC-{self.batch.batch_code}"


class StockTransaction(models.Model):
    """
    库存流水日志
    不可变的历史记录表。任何库存的增加或减少都必须在此留痕。
    用于财务对账和问题追溯。
    """
    TRANSACTION_TYPE_CHOICES = [
        ('inbound', 'Inbound Receipt'), # 入库
        ('outbound', 'Outbound Shipment'), # 出库
        ('adjust', 'Inventory Adjustment'), # 盘点/调整
        ('move', 'Location Move'), # 移库
    ]

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT)
    label_version = models.ForeignKey(LabelVersion, on_delete=models.PROTECT)
    location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT)
    
    # 变动数量：正数代表增加，负数代表减少
    quantity_change = models.IntegerField()
    # 变动后的结余（快照）
    balance_after = models.PositiveIntegerField()
    
    operator = models.ForeignKey(Operator, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # 关联单据号（可以是入库单号、出库单号等）
    reference_document = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.timestamp} | {self.transaction_type} | {self.quantity_change}"