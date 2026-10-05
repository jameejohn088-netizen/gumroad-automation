package com.gumroadautomation.data.repository

import com.google.gson.Gson
import com.google.gson.JsonParser
import com.gumroadautomation.data.api.dto.CustomerDto
import com.gumroadautomation.data.api.dto.DashboardDto
import com.gumroadautomation.data.api.dto.GumroadAccountDto
import com.gumroadautomation.data.api.dto.ProductDto
import com.gumroadautomation.data.api.dto.SaleDto
import com.gumroadautomation.data.api.dto.SubscriberDto
import com.gumroadautomation.data.db.entity.CachedAccount
import com.gumroadautomation.data.db.entity.CachedCustomer
import com.gumroadautomation.data.db.entity.CachedProduct
import com.gumroadautomation.data.db.entity.CachedSale
import com.gumroadautomation.data.db.entity.CachedSubscriber
import com.gumroadautomation.data.db.entity.DashboardSnapshot
import retrofit2.Response
import java.io.IOException

/** Extracts a human-readable message from an error response without leaking internals. */
fun parseError(response: Response<*>, gson: Gson = Gson()): String {
    val fallback = "Request failed (HTTP ${response.code()})"
    return try {
        val body = response.errorBody()?.string().orEmpty()
        if (body.isBlank()) return fallback
        val json = JsonParser.parseString(body)
        if (json.isJsonObject) {
            json.asJsonObject.get("message")?.asString
                ?: json.asJsonObject.get("detail")?.asString
                ?: fallback
        } else {
            fallback
        }
    } catch (_: Exception) {
        fallback
    }
}

/** Maps network failures to friendly messages (no stack traces to the UI). */
fun networkError(e: IOException): String =
    "No connection to the backend. Check the backend URL in Settings and try again."

// -- DTO -> cache entity mappers ------------------------------------------------

fun GumroadAccountDto.toCached() = CachedAccount(
    id = id,
    name = name,
    status = status,
    lastSyncAt = lastSyncAt,
)

fun ProductDto.toCached(accountScope: String) = CachedProduct(
    id = id,
    accountId = accountScope,
    name = name,
    priceCents = priceCents,
    currency = currency,
    published = published,
    thumbnailUrl = thumbnailUrl,
    salesCount = salesCount,
)

fun SaleDto.toCached(accountScope: String) = CachedSale(
    id = id,
    accountId = accountScope,
    productName = productName,
    email = email,
    amountCents = amountCents,
    currency = currency,
    refunded = refunded,
    shipped = shipped,
    createdAt = createdAt,
)

fun CustomerDto.toCached(accountScope: String) = CachedCustomer(
    id = id,
    accountId = accountScope,
    email = email,
    name = name,
    totalSpentCents = totalSpentCents,
    purchaseCount = purchaseCount,
)

fun SubscriberDto.toCached(accountScope: String) = CachedSubscriber(
    id = id,
    accountId = accountScope,
    email = email,
    productName = productName,
    status = status,
)

// -- cache entity -> DTO mappers (for offline display) --------------------------

fun CachedProduct.toDto() = ProductDto(
    id = id, accountId = accountId, name = name, priceCents = priceCents,
    currency = currency, published = published, thumbnailUrl = thumbnailUrl,
    salesCount = salesCount,
)

fun CachedSale.toDto() = SaleDto(
    id = id, accountId = accountId, productName = productName, email = email,
    amountCents = amountCents, currency = currency, refunded = refunded,
    shipped = shipped, createdAt = createdAt,
)

fun CachedCustomer.toDto() = CustomerDto(
    id = id, accountId = accountId, email = email, name = name,
    totalSpentCents = totalSpentCents, purchaseCount = purchaseCount,
)

fun CachedSubscriber.toDto() = SubscriberDto(
    id = id, accountId = accountId, email = email,
    productName = productName, status = status,
)

fun DashboardSnapshot.toDto(gson: Gson): DashboardDto {
    val sales: List<SaleDto> = try {
        val type = com.google.gson.reflect.TypeToken.getParameterized(
            List::class.java, SaleDto::class.java
        ).type
        gson.fromJson(recentSalesJson, type) ?: emptyList()
    } catch (_: Exception) {
        emptyList()
    }
    return DashboardDto(
        revenueCents = revenueCents,
        salesCount = salesCount,
        customersCount = customersCount,
        subscribersCount = subscribersCount,
        productsCount = productsCount,
        recentSales = sales,
    )
}
