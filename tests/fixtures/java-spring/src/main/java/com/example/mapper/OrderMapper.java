package com.example.mapper;

@org.apache.ibatis.annotations.Mapper
public interface OrderMapper {
    Object selectByStoreNo(String storeNo);
}
