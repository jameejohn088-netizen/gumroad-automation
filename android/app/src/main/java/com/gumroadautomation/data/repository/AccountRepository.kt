package com.gumroadautomation.data.repository

import com.gumroadautomation.data.api.ApiProvider
import com.gumroadautomation.data.api.dto.ConnectManualRequest
import com.gumroadautomation.data.api.dto.CreateAccountRequest
import com.gumroadautomation.data.api.dto.GumroadAccountDto
import com.gumroadautomation.data.api.dto.SyncHistoryDto
import com.gumroadautomation.data.api.dto.UpdateAccountRequest
import com.gumroadautomation.data.db.AppDatabase
import com.gumroadautomation.util.ApiResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Gumroad account management. There is no artificial account limit —
 * only real backend/Gumroad limits apply.
 */
@Singleton
class AccountRepository @Inject constructor(
    private val apiProvider: ApiProvider,
    private val database: AppDatabase,
) {
    fun accounts(): Flow<ApiResult<List<GumroadAccountDto>>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().listAccounts()
            if (res.isSuccessful) {
                val accounts = res.body().orEmpty()
                database.accountDao().upsertAll(accounts.map { it.toCached() })
                emit(ApiResult.Success(accounts))
            } else {
                emit(ApiResult.Error(parseError(res)))
            }
        } catch (e: IOException) {
            val cached = database.accountDao().getAll()
            if (cached.isNotEmpty()) {
                emit(
                    ApiResult.Error(
                        networkError(e),
                        cached.map {
                            GumroadAccountDto(
                                id = it.id, name = it.name, status = it.status,
                                lastSyncAt = it.lastSyncAt
                            )
                        },
                    )
                )
            } else {
                emit(ApiResult.Error(networkError(e)))
            }
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load accounts."))
        }
    }.flowOn(Dispatchers.IO)

    fun createAccount(name: String): Flow<ApiResult<GumroadAccountDto>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().createAccount(CreateAccountRequest(name.trim()))
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not create account."))
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Manual access-token connect (personal-use mode). The token is sent to OUR
     * backend over HTTPS and stored encrypted server-side — it is never persisted
     * on the device.
     */
    fun connectManual(accountId: String, accessToken: String): Flow<ApiResult<GumroadAccountDto>> =
        flow {
            emit(ApiResult.Loading)
            try {
                val res = apiProvider.service()
                    .connectManual(accountId, ConnectManualRequest(accessToken.trim()))
                if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
                else emit(ApiResult.Error(parseError(res)))
            } catch (e: IOException) {
                emit(ApiResult.Error(networkError(e)))
            } catch (_: Exception) {
                emit(ApiResult.Error("Connection failed. Check the token and try again."))
            }
        }.flowOn(Dispatchers.IO)

    private fun accountAction(
        accountId: String,
        action: suspend com.gumroadautomation.data.api.ApiService.(String) -> retrofit2.Response<GumroadAccountDto>,
    ): Flow<ApiResult<GumroadAccountDto>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().action(accountId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Action failed. Please try again."))
        }
    }.flowOn(Dispatchers.IO)

    fun disconnect(accountId: String) = accountAction(accountId) { disconnect(it) }
    fun reconnect(accountId: String) = accountAction(accountId) { reconnect(it) }
    fun enable(accountId: String) = accountAction(accountId) { enable(it) }
    fun disable(accountId: String) = accountAction(accountId) { disable(it) }

    /** Remove with cascade: also drops this account's cached rows on-device. */
    fun deleteAccount(accountId: String): Flow<ApiResult<String>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().deleteAccount(accountId)
            if (res.isSuccessful) {
                database.accountDao().delete(accountId)
                database.productDao().clearByAccount(accountId)
                database.saleDao().clearByAccount(accountId)
                database.customerDao().clearByAccount(accountId)
                database.subscriberDao().clearByAccount(accountId)
                emit(ApiResult.Success(res.body()?.message ?: "Account removed"))
            } else {
                emit(ApiResult.Error(parseError(res)))
            }
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not remove account."))
        }
    }.flowOn(Dispatchers.IO)

    fun syncNow(accountId: String): Flow<ApiResult<String>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().syncAccount(accountId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!.jobId))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not start sync."))
        }
    }.flowOn(Dispatchers.IO)

    fun syncHistory(accountId: String): Flow<ApiResult<List<SyncHistoryDto>>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().syncHistory(accountId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body().orEmpty()))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load sync history."))
        }
    }.flowOn(Dispatchers.IO)
}
