package com.example.controller;

import com.example.service.OrderService;

@org.springframework.web.bind.annotation.RestController
public class OrderController {
    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    public Object queryByStoreNo(String storeNo) {
        return orderService.findByStoreNo(storeNo);
    }
}
