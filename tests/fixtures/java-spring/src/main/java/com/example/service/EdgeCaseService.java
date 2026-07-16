package com.example.service;

public class EdgeCaseService {
    public void tricky(String storeNo) {
        String s = "}{ not a real brace ";
        /* } another fake brace } */
        doWork(storeNo);
    }

    public void after() {
        other();
    }
}
