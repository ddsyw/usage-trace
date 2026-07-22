from app.services.order_service import OrderService


class OrderApi:
    def __init__(self, service: OrderService):
        self.service = service

    def get_order(self, store_no: str):
        return self.service.find_by_store_no(store_no)
