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