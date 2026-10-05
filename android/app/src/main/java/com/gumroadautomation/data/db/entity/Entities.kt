package com.gumroadautomation.data.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Offline read-cache entities. They mirror the backend DTOs but exist only so the
 * app stays readable without a network connection. Writes always go to the backend;
 * the cache is refreshed on every successful network fetch (last-write-wins).
 */

@Entity(tableName = "cached_accounts")
data class CachedAccount(
    @PrimaryKey val id: String,
    val name: String,
    val status: String,
    val lastSyncAt: String?,
)

@Entity(
    tableName = "cached_products",
    // One product row per (account, gumroad product id).
)
data class CachedProduct(
    @PrimaryKey val id: String,
    val accountId: String,
    val name: String,
    val priceCents: Long,
    val currency: String?,
    val published: Boolean,
    val thumbnailUrl: String?,
    val salesCount: Int?,
)

@Entity(tableName = "cached_sales")
data class CachedSale(
    @PrimaryKey val id: String,
    val accountId: String,
    val productName: String?,
    val email: String?,
    val amountCents: Long,
    val currency: String?,
    val refunded: Boolean,
    val shipped: Boolean,
    val createdAt: String?,
)

@Entity(tableName = "cached_customers")
data class CachedCustomer(
    @PrimaryKey val id: String,
    val accountId: String,
    val email: String,
    val name: String?,
    val totalSpentCents: Long,
    val purchaseCount: Int,
)

@Entity(tableName = "cached_subscribers")
data class CachedSubscriber(
    @PrimaryKey val id: String,
    val accountId: String,
    val email: String,
    val productName: String?,
    val status: String?,
)

@Entity(tableName = "dashboard_snapshot")
data class DashboardSnapshot(
    @PrimaryKey val key: String = "dashboard",
    /** "all" or a concrete account id — the selector this snapshot belongs to. */
    val scope: String,
    val revenueCents: Long,
    val salesCount: Int,
    val customersCount: Int,
    val subscribersCount: Int,
    val productsCount: Int,
    /** JSON array of recent SaleDto, kept small on purpose. */
    val recentSalesJson: String,
    val updatedAt: Long,
)
