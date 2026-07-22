using Example.Services;
using Example.Data;

namespace Example.Controllers
{
    public class OrderController
    {
        private OrderService service;

        public OrderController(OrderService service)
        {
            this.service = service;
        }

        public Order Get(string storeNo)
        {
            return service.FindByStoreNo(storeNo);
        }
    }
}
