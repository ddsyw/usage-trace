namespace Example.Data
{
    public class OrderRepository
    {
        private AppDbContext db;

        public Order SelectByStoreNo(string storeNo)
        {
            var sql = "SELECT * FROM orders WHERE store_no = @storeNo";
            return null;
        }

        public Order FindOrders(string storeNo)
        {
            return SelectByStoreNo(storeNo);
        }

        public Order FindWithRawSql(string storeNo)
        {
            return db.Orders.FromSqlRaw("SELECT * FROM orders WHERE store_no = {0}", storeNo).FirstOrDefault();
        }
    }

    public class AppDbContext
    {
        public DbSet<Order> Orders { get; set; }
    }
}
