"""
Packages Controller for H28 API.
Handles CRUD operations for telecom service packages.
"""

from flask import request, url_for
from flask_restx import Namespace, Resource, fields
from ...utils.pageable import Pageable
from ...utils.hateoas import HATEOAS
from ...utils.db import serialize_mongo_doc
from ...services.JWTAuthService import require_auth

#######################################
## STEP 1. DECLARE THE API NAMESPACE ##
#######################################

api = Namespace('local-knowledge/packages', description='Quản lý gói cước viễn thông')

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

package_create_dto = api.model("PackageCreate", {
    "Mã dịch vụ": fields.String(required=True, description="Mã dịch vụ gói cước"),
    "Thời gian thanh toán": fields.String(required=True, description="Trả trước/trả sau"),
    "Các dịch vụ tiên quyết": fields.String(required=True, description="Các dịch vụ cần có"),
    "Giá (VNĐ)": fields.Integer(required=True, description="Giá gói cước (VNĐ)"),
    "Chu kỳ (ngày)": fields.Integer(required=True, description="Chu kỳ gói cước (ngày)"),
    "4G tốc độ tiêu chuẩn/ngày": fields.Float(required=True, description="Dung lượng 4G tốc độ tiêu chuẩn mỗi ngày (GB)"),
    "4G tốc độ cao/ngày": fields.Float(required=True, description="Dung lượng 4G tốc độ cao mỗi ngày (GB)"),
    "4G tốc độ tiêu chuẩn/chu kỳ": fields.Float(required=True, description="Dung lượng 4G tốc độ tiêu chuẩn mỗi chu kỳ (GB)"),
    "4G tốc độ cao/chu kỳ": fields.Float(required=True, description="Dung lượng 4G tốc độ cao mỗi chu kỳ (GB)"),
    "Gọi nội mạng": fields.String(required=True, description="Thông tin gọi nội mạng"),
    "Gọi ngoại mạng": fields.String(required=True, description="Thông tin gọi ngoại mạng"),
    "Tin nhắn": fields.String(required=True, description="Thông tin tin nhắn"),
    "Chi tiết": fields.String(required=True, description="Thông tin chi tiết gói cước"),
    "Tự động gia hạn": fields.String(required=True, description="Thông tin tự động gia hạn"),
    "Cú pháp đăng ký": fields.String(required=True, description="Cú pháp đăng ký gói cước"),
})

package_update_dto = api.model("PackageUpdate", {
    "Mã dịch vụ": fields.String(required=False),
    "Thời gian thanh toán": fields.String(required=False),
    "Các dịch vụ tiên quyết": fields.String(required=False),
    "Giá (VNĐ)": fields.Integer(required=False),
    "Chu kỳ (ngày)": fields.Integer(required=False),
    "4G tốc độ tiêu chuẩn/ngày": fields.Float(required=False),
    "4G tốc độ cao/ngày": fields.Float(required=False),
    "4G tốc độ tiêu chuẩn/chu kỳ": fields.Float(required=False),
    "4G tốc độ cao/chu kỳ": fields.Float(required=False),
    "Gọi nội mạng": fields.String(required=False),
    "Gọi ngoại mạng": fields.String(required=False),
    "Tin nhắn": fields.String(required=False),
    "Chi tiết": fields.String(required=False),
    "Tự động gia hạn": fields.String(required=False),
    "Cú pháp đăng ký": fields.String(required=False),
})

package_dto = api.clone("Package", package_create_dto, {
    "id": fields.String(readonly=True, description="ID của gói cước"),
})

delete_response_dto = api.model("DeleteResponse", {
    "message": fields.String(description="Thông báo kết quả")
})

##################################
## STEP 3. CONNECT THE SERVICES ##
##################################

from ...services import package_service

###################################
## STEP 4. DEFINE THE CONTROLLER ##
###################################

h = HATEOAS(api)


@api.route("/")
class PackageCollection(Resource):
    service = package_service

    get_collection_qp = Pageable.pageable_query_params()

    @api.doc(description="Lấy danh sách tất cả các gói cước, có pagination.")
    @h.expect(get_collection_qp)
    @h.returns(
        package_dto,
        as_list=True,
        self_links=lambda content: [],
        collection_links=lambda content: [url_for("v1.local-knowledge/packages_package_collection")],
    )
    @require_auth
    def get(self):
        args = self.get_collection_qp.parse_args()
        pageable = Pageable.from_query_params(args)
        return self.service.get_collection(pageable)

    @api.doc(description="Thêm gói cước mới (TP-07).")
    @h.expect(package_create_dto)
    @h.returns(
        package_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/packages_package_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/packages_package_collection")],
    )
    @require_auth
    def post(self):
        data = request.get_json()
        result = self.service.post_item(data)
        return serialize_mongo_doc(result)


@api.route("/<string:id>")
class PackageItem(Resource):
    service = package_service

    @api.doc(description="Lấy thông tin gói cước theo ID.")
    @h.returns(
        package_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/packages_package_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/packages_package_collection")],
    )
    @require_auth
    def get(self, id):
        result = self.service.get_item_by_id(id)
        return serialize_mongo_doc(result)

    @api.doc(description="Cập nhật gói cước theo ID (TP-08).")
    @h.expect(package_update_dto)
    @h.returns(
        package_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/packages_package_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/packages_package_collection")],
    )
    @require_auth
    def patch(self, id):
        data = request.get_json()
        result = self.service.patch_item_by_id(id, data)
        return serialize_mongo_doc(result)

    @api.doc(description="Xóa gói cước theo ID (TP-09).")
    @h.returns(
        delete_response_dto,
        self_links=lambda content: [],
        collection_links=lambda content: [url_for("v1.local-knowledge/packages_package_collection")],
    )
    @require_auth
    def delete(self, id):
        self.service.delete_item_by_id(id)
        return {"message": "Package deleted successfully"}
