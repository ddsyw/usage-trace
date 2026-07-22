using Example.Data;

namespace Example.Services
{
    public class OrderService
    {
        private OrderRepository repo;

        public OrderService(OrderRepository repo)
        {
            this.repo = repo;
        }

        public Order FindByStoreNo(string storeNo)
        {
            return repo.FindOrders(storeNo);
        }
    }
}
