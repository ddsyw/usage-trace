using System.ComponentModel.DataAnnotations.Schema;

namespace Example.Data
{
    [Table("orders")]
    public class Order
    {
        public int Id { get; set; }
        public string StoreNo { get; set; }
    }
}
