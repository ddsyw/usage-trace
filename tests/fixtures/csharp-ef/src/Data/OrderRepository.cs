namespace Example.Data
{
    public class OrderRepository
    {
        public Order SelectByStoreNo(string storeNo)
        {
            var sql = "SELECT * FROM orders WHERE store_no = @storeNo";
            return null;
        }

        public Order FindOrders(string storeNo)
        {
            return SelectByStoreNo(storeNo);
        }
    }
}
