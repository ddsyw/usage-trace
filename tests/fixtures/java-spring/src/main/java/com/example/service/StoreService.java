package com.example.service;

@org.springframework.stereotype.Service
public class StoreService {
    // Same method name as OrderService.findByStoreNo — exercises ambiguity handling.
    public Object findByStoreNo(String storeNo) {
        return null;
    }
}
