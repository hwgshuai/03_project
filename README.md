### 项目结构
```
warehouse_project/
├── warehouse_project/      # Django 项目配置
│   ├── settings.py        # 项目设置
│   ├── urls.py           # URL 路由配置
│   ├── wsgi.py           # WSGI 配置
│   └── asgi.py           # ASGI 配置
├── warehouse/             # 核心应用
│   ├── models.py         # 数据模型定义
│   ├── views.py          # API 视图
│   ├── serializers.py    # 数据序列化器
│   ├── admin.py          # 管理员界面配置
│   ├── urls.py           # 应用路由
│   ├── utils.py          # 工具函数
│   └── migrations/       # 数据库迁移文件
├── manage.py             # Django 管理脚本
├── db.sqlite3           # SQLite 数据库文件
└── test_api.html        # API 测试界面
```

## 数据模型结构说明

### 1. Operator (操作员/审核员)
```python
class Operator(models.Model):
    username = models.CharField(max_length=50, unique=True, verbose_name="Username")
    full_name = models.CharField(max_length=100, blank=True, verbose_name="Full Name")
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```
- **功能**: 管理系统用户信息，包括创建人和审核人
- **字段**: 用户名、全名、邮箱、激活状态、创建时间

### 2. SKU (库存单位)
```python
class SKU(models.Model):
    sku_code = models.CharField(max_length=100, unique=True)
    product_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```
- **功能**: 管理产品库存单位信息
- **字段**: SKU 编码、产品名称、创建时间

### 3. LabelVersion (标签版本)
```python
class LabelVersion(models.Model):
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    version_number = models.IntegerField()
    fnsku = models.CharField(max_length=100, blank=True)
    upc = models.CharField(max_length=100, blank=True)
    created_by = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    checksum = models.CharField(max_length=64, editable=False)
```
- **功能**: 管理产品标签的不同版本，包含自动生成的校验和
- **关键特性**:
  - 版本号自动递增
  - 基于 FNSKU 和 UPC 生成 SHA256 校验和
  - 版本唯一性约束（SKU + 版本号）

### 4. ShipmentBatch (出货批次)
```python
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
```
- **功能**: 管理出货批次，包含完整的多级审核流程
- **审核机制**:
  - 一级审核：reviewer1 字段
  - 二级审核：reviewer2 字段
  - 自审核防护：审核人不能是创建人
  - 重复审核防护：一级和二级审核人不能是同一个人
  - 状态自动更新：基于审核结果自动更新批次状态

## 已实现的功能特性

### ✅ 核心功能模块

#### 1. SKU 管理
- **功能**: SKU 信息的增删改查
- **API端点**: `/api/skus/`
- **管理后台**: 完整的 Django Admin 管理界面

#### 2. 标签版本控制
- **功能**:
  - 自动版本号管理
  - 基于内容生成 SHA256 校验和
  - 版本历史追踪
- **API端点**: `/api/labels/`
- **关键特性**: 每次创建新标签会自动递增版本号

#### 3. 出货批次管理
- **功能**:
  - 批次信息创建和管理
  - 多级审核流程（两级审核）
  - 审核风险控制
  - 状态自动更新
- **API端点**: `/api/batches/`
- **审核接口**: `/api/batches/{id}/review/`

#### 4. 审核风控系统
- **风险控制**:
  - **自审核防护**: 审核人不能审核自己创建的批次
  - **重复审核防护**: 一级和二级审核人不能是同一个人
  - **状态机**: 自动根据审核结果更新批次状态
- **状态定义**:
  - `pending`: 待审核
  - `reviewing`: 审核中
  - `approved`: 已批准
  - `rejected`: 已拒绝

#### 5. 操作员管理
- **功能**: 管理系统中的所有操作员和审核员
- **Admin界面**: 完整的用户管理功能

### ✅ 技术特性

#### Django Admin 集成
- **定制化表单**: SKU 创建表单带有初始标签信息
- **权限控制**: 标签版本修改权限限制
- **智能查询**: 审核人选择只显示激活用户

#### REST API
- **完整的 CRUD 操作**: 对所有模型的全面支持
- **嵌套序列化**: 提供详细的外键关联信息
- **自定义动作**: 审核功能通过自定义动作实现

#### 安全防护
- **内容校验**: 自动生成 SHA256 校验和
- **审核链完整性**: 多级审核机制确保操作安全
- **权限验证**: 多层权限验证机制

## 代码运行逻辑

### 1. 标签版本创建流程
```
1. 用户提交 FNSKU 和 UPC 信息
2. 系统自动查找该 SKU 的最新版本号
3. 版本号自动递增（从 0 开始）
4. 基于 FNSKU+UPC 生成 SHA256 校验和
5. 保存新版本的完整信息
```

### 2. 出货批次审核流程
```
1. 创建批次：初始状态为 'pending'
2. 一级审核：通过专用审核接口提交
   - 验证审核人与创建人不同
   - 记录审核信息和时间
   - 更新批次状态
3. 二级审核：通过专用审核接口提交
   - 验证审核人与一级审核人不同
   - 验证审核人与创建人不同
   - 记录审核信息和时间
   - 最终确定批次状态
4. 状态确定：根据两级审核结果确定最终状态
```

### 3. 风险控制机制
```python
# 自审核检查
if batch.created_by and batch.created_by.id == operator.id:
    return Response({"error": "Reviewer cannot be the creator."}, status=403)

# 重复审核检查
if batch.reviewer2 and batch.reviewer2.id == operator.id:
    return Response({"error": "Reviewer 1 cannot be the same as Reviewer 2."}, status=403)
```

## 数据库设计说明

### 表关系结构
```
SKU (1) -----> (N) LabelVersion
   |
   |
   -----> (N) ShipmentBatch
           |
           |
           -----> (1) LabelVersion
```

### 关键约束
- **SKU**: sku_code 必须唯一
- **LabelVersion**: (sku, version_number) 组合唯一
- **ShipmentBatch**: batch_code 必须唯一
- **Operator**: username 必须唯一

### 数据完整性
- 外键完整性：所有外键关系都有适当的级联和限制
- 业务完整性：版本号自动递增、审核逻辑完整
- 审计完整性：所有关键操作都有时间戳和操作者记录

## 管理员功能说明

### Django Admin 界面特性

#### 1. Operator 管理
- **列表显示**: 用户名、全名、邮箱、激活状态
- **搜索功能**: 支持用户名和全名搜索
- **编辑功能**: 完整的创建、编辑、删除

#### 2. SKU 管理
- **创建集成**: 创建 SKU 时可同时创建初始标签版本
- **自动处理**: 保存 SKU 后自动调用标签版本创建
- **列表显示**: SKU 编码、产品名称、创建时间

#### 3. LabelVersion 管理
- **版本控制**: 版本号和校验和为只读字段
- **修改限制**: 禁止修改已创建的版本
- **显示优化**: 显示 SKU 编码和版本详情

#### 4. ShipmentBatch 管理
- **状态控制**: 状态字段为只读，自动更新
- **审核人筛选**: 审核人选择只显示激活的操作员
- **审核追踪**: 显示完整的审核历史和意见
- **批量操作**: 支持批量状态更新

## API 接口文档

### SKU API
- `GET /api/skus/` - 获取 SKU 列表
- `POST /api/skus/` - 创建新 SKU
- `GET /api/skus/{id}/` - 获取特定 SKU
- `PUT /api/skus/{id}/` - 更新 SKU
- `DELETE /api/skus/{id}/` - 删除 SKU

### LabelVersion API
- `GET /api/labels/` - 获取标签版本列表
- `POST /api/labels/` - 创建新标签版本
- `GET /api/labels/{id}/` - 获取特定标签版本
- `PUT /api/labels/{id}/` - 更新标签版本
- `DELETE /api/labels/{id}/` - 删除标签版本

### ShipmentBatch API
- `GET /api/batches/` - 获取批次列表
- `POST /api/batches/` - 创建新批次
- `GET /api/batches/{id}/` - 获取特定批次
- `PUT /api/batches/{id}/` - 更新批次
- `DELETE /api/batches/{id}/` - 删除批次
- `POST /api/batches/{id}/review/` - 审核批次
  ```json
  {
    "reviewer_role": "1" | "2",
    "approved": true | false,
    "comment": "审核意见",
    "operator_id": 1
  }
  ```

## 测试和验证

### 提供测试工具
- **API 测试页面**: `test_api.html` 提供可视化的 API 测试界面
- **功能覆盖**: 支持 SKU 查询和标签版本创建操作
- **错误处理**: 完整的错误提示和状态显示

### 快速开始
1. 运行服务器：`python manage.py runserver`
2. 打开测试页面：访问 `http://127.0.0.1:8000/test_api.html`
3. 管理员界面：访问 `http://127.0.0.1:8000/admin/`

## 开发环境配置

### 必要依赖
- Django 5.2.8
- Django REST Framework
- Django CORS Headers

### 运行环境
- Python 3.8+
- SQLite 数据库
- 支持的操作系统：Windows、Linux、macOS