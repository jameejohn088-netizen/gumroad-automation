package com.gumroadautomation.data.repository

import com.gumroadautomation.data.api.ApiProvider
import com.gumroadautomation.data.api.dto.ActionResultDto
import com.gumroadautomation.data.api.dto.CustomerDto
import com.gumroadautomation.data.api.dto.DryRunRequest
import com.gumroadautomation.data.api.dto.LicenseDto
import com.gumroadautomation.data.api.dto.MembershipDto
import com.gumroadautomation.data.api.dto.PageResponse
import com.gumroadautomation.data.api.dto.ProductDto
import com.gumroadautomation.data.api.dto.SaleDto
import com.gumroadautomation.data.api.dto.SubscriberDto
import com.gumroadautomation.data.db.AppDatabase
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.Constants
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Catalog data (products, sales, customers, subscribers, licenses, memberships).
 * First page is cached to Room for offline reading; search/pagination always hit
 * the backend when online.
 */
@Singleton
class CatalogRepository @Inject constructor(
    private val apiProvider: ApiProvider,
    private val database: AppDatabase,
) {
    private fun scopeOf(accountId: String?): String = accountId ?: "all"
    private fun queryOf(q: String?): String? = q?.trim()?.ifEmpty { null }

    fun products(
        accountId: String?,
        q: String?,
        page: Int,
    ): Flow<ApiResult<PageResponse<ProductDto>>> = flow {
        emit(ApiResult.Loading)
        val scope = scopeOf(accountId)
        try {
            val res = apiProvider.service()
                .products(accountId, queryOf(q), page, Constants.PAGE_SIZE)
            if (res.isSuccessful) {
                val body = res.body()!!
                if (page == 1 && queryOf(q) == null) {
                    database.productDao().clearByAccount(scope)
                    database.productDao().upsertAll(body.items.map { it.toCached(scope) })
                }
                emit(ApiResult.Success(body))
            } else {
                emit(ApiResult.Error(parseError(res)))
            }
        } catch (e: IOException) {
            val cached = database.productDao().getByAccount(scope)
            val ql = queryOf(q)?.lowercase().orEmpty()
            val filtered = if (ql.isEmpty()) cached
            else cached.filter { it.name.lowercase().contains(ql) }
            emit(
                ApiResult.Error(
                    networkError(e),
                    PageResponse(
                        items = filtered.map { it.toDto() },
                        total = filtered.size, page = 1, perPage = filtered.size
                    ),
                )
            )
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load products."))
        }
    }.flowOn(Dispatchers.IO)

    fun sales(
        accountId: String?,
        q: String?,
        page: Int,
    ): Flow<ApiResult<PageResponse<SaleDto>>> = flow {
        emit(ApiResult.Loading)
        val scope = scopeOf(accountId)
        try {
            val res = apiProvider.service()
                .sales(accountId, queryOf(q), page, Constants.PAGE_SIZE)
            if (res.isSuccessful) {
                val body = res.body()!!
                if (page == 1 && queryOf(q) == null) {
                    database.saleDao().clearByAccount(scope)
                    database.saleDao().upsertAll(body.items.map { it.toCached(scope) })
                }
                emit(ApiResult.Success(body))
            } else {
                emit(ApiResult.Error(parseError(res)))
            }
        } catch (e: IOException) {
            val cached = database.saleDao().getByAccount(scope)
            val ql = queryOf(q)?.lowercase().orEmpty()
            val filtered = if (ql.isEmpty()) cached
            else cached.filter {
                (it.productName?.lowercase()?.contains(ql) == true) ||
                    (it.email?.lowercase()?.contains(ql) == true)
            }
            emit(
                ApiResult.Error(
                    networkError(e),
                    PageResponse(
                        items = filtered.map { it.toDto() },
                        total = filtered.size, page = 1, perPage = filtered.size
                    ),
                )
            )
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load sales."))
        }
    }.flowOn(Dispatchers.IO)

    fun customers(
        accountId: String?,
        q: String?,
        page: Int,
    ): Flow<ApiResult<PageResponse<CustomerDto>>> = flow {
        emit(ApiResult.Loading)
        val scope = scopeOf(accountId)
        try {
            val res = apiProvider.service()
                .customers(accountId, queryOf(q), page, Constants.PAGE_SIZE)
            if (res.isSuccessful) {
                val body = res.body()!!
                if (page == 1 && queryOf(q) == null) {
                    database.customerDao().clearByAccount(scope)
                    database.customerDao().upsertAll(body.items.map { it.toCached(scope) })
                }
                emit(ApiResult.Success(body))
            } else {
                emit(ApiResult.Error(parseError(res)))
            }
        } catch (e: IOException) {
            val cached = database.customerDao().getByAccount(scope)
            val ql = queryOf(q)?.lowercase().orEmpty()
            val filtered = if (ql.isEmpty()) cached
            else cached.filter { it.email.lowercase().contains(ql) }
            emit(
                ApiResult.Error(
                    networkError(e),
                    PageResponse(
                        items = filtered.map { it.toDto() },
                        total = filtered.size, page = 1, perPage = filtered.size
                    ),
                )
            )
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load customers."))
        }
    }.flowOn(Dispatchers.IO)

    fun subscribers(
        accountId: String?,
        q: String?,
        page: Int,
    ): Flow<ApiResult<PageResponse<SubscriberDto>>> = flow {
        emit(ApiResult.Loading)
        val scope = scopeOf(accountId)
        try {
            val res = apiProvider.service()
                .subscribers(accountId, queryOf(q), page, Constants.PAGE_SIZE)
            if (res.isSuccessful) {
                val body = res.body()!!
                if (page == 1 && queryOf(q) == null) {
                    database.subscriberDao().clearByAccount(scope)
                    database.subscriberDao().upsertAll(body.items.map { it.toCached(scope) })
                }
                emit(ApiResult.Success(body))
            } else {
                emit(ApiResult.Error(parseError(res)))
            }
        } catch (e: IOException) {
            val cached = database.subscriberDao().getByAccount(scope)
            val ql = queryOf(q)?.lowercase().orEmpty()
            val filtered = if (ql.isEmpty()) cached
            else cached.filter { it.email.lowercase().contains(ql) }
            emit(
                ApiResult.Error(
                    networkError(e),
                    PageResponse(
                        items = filtered.map { it.toDto() },
                        total = filtered.size, page = 1, perPage = filtered.size
                    ),
                )
            )
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load subscribers."))
        }
    }.flowOn(Dispatchers.IO)

    fun licenses(
        accountId: String?,
        q: String?,
        page: Int,
    ): Flow<ApiResult<PageResponse<LicenseDto>>> = paged(
        fetcher = { apiProvider.service().licenses(accountId, queryOf(q), page, Constants.PAGE_SIZE) },
        errorMessage = "Could not load licenses.",
    )

    fun memberships(
        accountId: String?,
        q: String?,
        page: Int,
    ): Flow<ApiResult<PageResponse<MembershipDto>>> = paged(
        fetcher = { apiProvider.service().memberships(accountId, queryOf(q), page, Constants.PAGE_SIZE) },
        errorMessage = "Could not load memberships.",
    )

    private fun <T> paged(
        fetcher: suspend () -> retrofit2.Response<PageResponse<T>>,
        errorMessage: String,
    ): Flow<ApiResult<PageResponse<T>>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = fetcher()
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error(errorMessage))
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Refund a sale. [dryRun] defaults to true — the UI requires explicit
     * confirmation before sending dry_run=false.
     */
    fun refundSale(saleId: String, dryRun: Boolean): Flow<ApiResult<ActionResultDto>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().refundSale(saleId, DryRunRequest(dryRun))
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Refund failed. Please try again."))
        }
    }.flowOn(Dispatchers.IO)

    fun markShipped(saleId: String, dryRun: Boolean): Flow<ApiResult<ActionResultDto>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().markShipped(saleId, DryRunRequest(dryRun))
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Mark-as-shipped failed. Please try again."))
        }
    }.flowOn(Dispatchers.IO)

    fun resendReceipt(saleId: String, dryRun: Boolean): Flow<ApiResult<ActionResultDto>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().resendReceipt(saleId, DryRunRequest(dryRun))
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Resend receipt failed. Please try again."))
        }
    }.flowOn(Dispatchers.IO)
}
