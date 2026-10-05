package com.gumroadautomation.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.gumroadautomation.data.db.entity.CachedAccount
import com.gumroadautomation.data.db.entity.CachedCustomer
import com.gumroadautomation.data.db.entity.CachedProduct
import com.gumroadautomation.data.db.entity.CachedSale
import com.gumroadautomation.data.db.entity.CachedSubscriber
import com.gumroadautomation.data.db.entity.DashboardSnapshot

@Dao
interface AccountDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(accounts: List<CachedAccount>)

    @Query("SELECT * FROM cached_accounts ORDER BY name")
    suspend fun getAll(): List<CachedAccount>

    @Query("DELETE FROM cached_accounts WHERE id = :accountId")
    suspend fun delete(accountId: String)

    @Query("DELETE FROM cached_accounts")
    suspend fun clear()
}

@Dao
interface ProductDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(products: List<CachedProduct>)

    @Query("SELECT * FROM cached_products WHERE accountId = :accountId OR :accountId = 'all' ORDER BY name")
    suspend fun getByAccount(accountId: String): List<CachedProduct>

    @Query("DELETE FROM cached_products WHERE accountId = :accountId")
    suspend fun clearByAccount(accountId: String)
}

@Dao
interface SaleDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(sales: List<CachedSale>)

    @Query(
        "SELECT * FROM cached_sales WHERE accountId = :accountId OR :accountId = 'all' " +
            "ORDER BY createdAt DESC"
    )
    suspend fun getByAccount(accountId: String): List<CachedSale>

    @Query("DELETE FROM cached_sales WHERE accountId = :accountId")
    suspend fun clearByAccount(accountId: String)
}

@Dao
interface CustomerDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(customers: List<CachedCustomer>)

    @Query("SELECT * FROM cached_customers WHERE accountId = :accountId OR :accountId = 'all' ORDER BY totalSpentCents DESC")
    suspend fun getByAccount(accountId: String): List<CachedCustomer>

    @Query("DELETE FROM cached_customers WHERE accountId = :accountId")
    suspend fun clearByAccount(accountId: String)
}

@Dao
interface SubscriberDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(subscribers: List<CachedSubscriber>)

    @Query("SELECT * FROM cached_subscribers WHERE accountId = :accountId OR :accountId = 'all' ORDER BY email")
    suspend fun getByAccount(accountId: String): List<CachedSubscriber>

    @Query("DELETE FROM cached_subscribers WHERE accountId = :accountId")
    suspend fun clearByAccount(accountId: String)
}

@Dao
interface DashboardDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(snapshot: DashboardSnapshot)

    @Query("SELECT * FROM dashboard_snapshot WHERE scope = :scope LIMIT 1")
    suspend fun get(scope: String): DashboardSnapshot?

    @Query("DELETE FROM dashboard_snapshot WHERE scope = :scope")
    suspend fun clear(scope: String)
}
