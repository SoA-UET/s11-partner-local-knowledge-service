"""
FAQs Controller for H28 API.
Handles CRUD operations for frequently asked questions.
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

api = Namespace('local-knowledge/faqs', description='Quản lý câu hỏi thường gặp (FAQ)')

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

faq_create_dto = api.model("FAQCreate", {
    "question": fields.String(required=True, description="Nội dung câu hỏi"),
    "answer": fields.String(required=True, description="Nội dung câu trả lời"),
})

faq_update_dto = api.model("FAQUpdate", {
    "question": fields.String(required=False, description="Nội dung câu hỏi"),
    "answer": fields.String(required=False, description="Nội dung câu trả lời"),
})

faq_dto = api.clone("FAQ", faq_create_dto, {
    "id": fields.String(readonly=True, description="ID của FAQ"),
})

delete_response_dto = api.model("DeleteResponse", {
    "message": fields.String(description="Thông báo kết quả")
})

##################################
## STEP 3. CONNECT THE SERVICES ##
##################################

from ...services import faq_service

###################################
## STEP 4. DEFINE THE CONTROLLER ##
###################################

h = HATEOAS(api)


@api.route("/")
class FAQCollection(Resource):
    service = faq_service

    get_collection_qp = Pageable.pageable_query_params()

    @api.doc(description="Lấy danh sách tất cả các FAQ, có pagination.")
    @h.expect(get_collection_qp)
    @h.returns(
        faq_dto,
        as_list=True,
        self_links=lambda content: [],
        collection_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_collection")],
    )
    @require_auth
    def get(self):
        args = self.get_collection_qp.parse_args()
        pageable = Pageable.from_query_params(args)
        return self.service.get_collection(pageable)

    @api.doc(description="Thêm FAQ mới (TP-10).")
    @h.expect(faq_create_dto)
    @h.returns(
        faq_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_collection")],
    )
    @require_auth
    def post(self):
        data = request.get_json()
        result = self.service.post_item(data)
        return serialize_mongo_doc(result)


@api.route("/<string:id>")
class FAQItem(Resource):
    service = faq_service

    @api.doc(description="Lấy thông tin FAQ theo ID.")
    @h.returns(
        faq_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_collection")],
    )
    @require_auth
    def get(self, id):
        result = self.service.get_item_by_id(id)
        return serialize_mongo_doc(result)

    @api.doc(description="Cập nhật FAQ theo ID (TP-11).")
    @h.expect(faq_update_dto)
    @h.returns(
        faq_dto,
        self_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_item", id=content["id"])],
        collection_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_collection")],
    )
    @require_auth
    def patch(self, id):
        data = request.get_json()
        result = self.service.patch_item_by_id(id, data)
        return serialize_mongo_doc(result)

    @api.doc(description="Xóa FAQ theo ID (TP-12).")
    @h.returns(
        delete_response_dto,
        self_links=lambda content: [],
        collection_links=lambda content: [url_for("v1.local-knowledge/faqs_faq_collection")],
    )
    @require_auth
    def delete(self, id):
        self.service.delete_item_by_id(id)
        return {"message": "FAQ deleted successfully"}
