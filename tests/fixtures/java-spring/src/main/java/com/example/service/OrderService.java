package com.example.service;

import com.example.mapper.OrderMapper;

@org.springframework.stereotype.Service
public class OrderService {
    private final OrderMapper orderMapper;

    public OrderService(OrderMapper orderMapper) {
        this.orderMapper = orderMapper;
    }

    public Object findByStoreNo(String storeNo) {
        return orderMapper.selectByStoreNo(storeNo);
    }
}
