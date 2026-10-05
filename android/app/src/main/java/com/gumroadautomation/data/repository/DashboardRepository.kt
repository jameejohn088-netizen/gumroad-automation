package com.gumroadautomation.data.repository

import com.google.gson.Gson
import com.gumroadautomation.data.api.ApiProvider
import com.gumroadautomation.data.api.dto.DashboardDto
import com.gumroadautomation.data.db.AppDatabase
import com.gumroadautomation.data.db.entity.DashboardSnapshot
import com.gumroadautomation.util.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DashboardRepository @Inject constructor(
    private val apiProvider: ApiProvider,
    private val database: AppDatabase,
    private val gson: Gson,
) {
    /** [accountId] null = "All Accounts" aggregate. */
    fun dashboard(accountId: String?): Flow<ApiResult<DashboardDto>> = flow {
        emit(ApiResult.Loading)
        val scope = accountId ?: "all"
        try {
            val res = apiProvider.service().dashboard(accountId)
            if (res.isSuccessful) {
                val dto = res.body()!!
                database.dashboardDao().upsert(
                    DashboardSnapshot(
                        scope = scope,
                        revenueCents = dto.revenueCents,
                        salesCount = dto.salesCount,
                        customersCount = dto.customersCount,
                        subscribersCount = dto.subscribersCount,
                        productsCount = dto.productsCount,
                        recentSalesJson = gson.toJson(dto.recentSales),
                        updatedAt = System.currentTimeMillis(),
                    )
                )
                emit(ApiResult.Success(dto))
            } else {
                emit(ApiResult.Error(parseError(res)))
            }
        } catch (e: IOException) {
            val cached = database.dashboardDao().get(scope)?.toDto(gson)
            if (cached != null) emit(ApiResult.Error(networkError(e), cached))
            else emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load dashboard."))
        }
    }.flowOn(Dispatchers.IO)
}
