class OrderRepository:
    def select_by_store_no(self, store_no: str):
        sql = "SELECT * FROM orders WHERE store_no = :store_no"
        return sql

    def find_orders(self, store_no: str):
        return self.select_by_store_no(store_no)


class OrderService:
    def __init__(self, repo: OrderRepository):
        self.repo = repo

    def find_by_store_no(self, store_no: str):
        return self.repo.find_orders(store_no)
