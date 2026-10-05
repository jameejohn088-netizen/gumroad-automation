package com.gumroadautomation.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.gumroadautomation.data.db.dao.AccountDao
import com.gumroadautomation.data.db.dao.CustomerDao
import com.gumroadautomation.data.db.dao.DashboardDao
import com.gumroadautomation.data.db.dao.ProductDao
import com.gumroadautomation.data.db.dao.SaleDao
import com.gumroadautomation.data.db.dao.SubscriberDao
import com.gumroadautomation.data.db.entity.CachedAccount
import com.gumroadautomation.data.db.entity.CachedCustomer
import com.gumroadautomation.data.db.entity.CachedProduct
import com.gumroadautomation.data.db.entity.CachedSale
import com.gumroadautomation.data.db.entity.CachedSubscriber
import com.gumroadautomation.data.db.entity.DashboardSnapshot

/**
 * Offline read cache. Version 1. Migrations must be added (not destructive) once
 * the app ships to real devices.
 */
@Database(
    entities = [
        CachedAccount::class,
        CachedProduct::class,
        CachedSale::class,
        CachedCustomer::class,
        CachedSubscriber::class,
        DashboardSnapshot::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun accountDao(): AccountDao
    abstract fun productDao(): ProductDao
    abstract fun saleDao(): SaleDao
    abstract fun customerDao(): CustomerDao
    abstract fun subscriberDao(): SubscriberDao
    abstract fun dashboardDao(): DashboardDao
}
