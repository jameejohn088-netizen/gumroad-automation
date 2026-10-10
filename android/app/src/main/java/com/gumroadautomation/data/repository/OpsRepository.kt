package com.gumroadautomation.data.repository

import com.gumroadautomation.data.api.ApiProvider
import com.gumroadautomation.data.api.dto.ActivityLogDto
import com.gumroadautomation.data.api.dto.ErrorLogDto
import com.gumroadautomation.data.api.dto.JobDto
import com.gumroadautomation.data.api.dto.JobExecutionDto
import com.gumroadautomation.data.api.dto.JobRequest
import com.gumroadautomation.data.api.dto.NotificationDto
import com.gumroadautomation.data.api.dto.PageResponse
import com.gumroadautomation.util.ApiResult
import com.gumroadautomation.util.Constants
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/** Jobs/scheduler, notifications, and activity/error logs. */
@Singleton
class OpsRepository @Inject constructor(
    private val apiProvider: ApiProvider,
) {
    fun jobs(accountId: String?): Flow<ApiResult<List<JobDto>>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().listJobs(accountId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body().orEmpty()))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load jobs."))
        }
    }.flowOn(Dispatchers.IO)

    fun saveJob(jobId: String?, request: JobRequest): Flow<ApiResult<JobDto>> = flow {
        emit(ApiResult.Loading)
        try {
            val api = apiProvider.service()
            val res = if (jobId == null) api.createJob(request) else api.updateJob(jobId, request)
            if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not save job."))
        }
    }.flowOn(Dispatchers.IO)

    fun deleteJob(jobId: String): Flow<ApiResult<String>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().deleteJob(jobId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body()?.message ?: "Job deleted"))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not delete job."))
        }
    }.flowOn(Dispatchers.IO)

    fun runJobNow(jobId: String): Flow<ApiResult<String>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().runJob(jobId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body()?.message ?: "Job started"))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not start job."))
        }
    }.flowOn(Dispatchers.IO)

    fun executions(jobId: String): Flow<ApiResult<List<JobExecutionDto>>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().jobExecutions(jobId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body().orEmpty()))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load executions."))
        }
    }.flowOn(Dispatchers.IO)

    fun retryExecution(jobId: String, execId: String): Flow<ApiResult<String>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().retryExecution(execId)
            if (res.isSuccessful) emit(ApiResult.Success(res.body()?.message ?: "Retry queued"))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not retry execution."))
        }
    }.flowOn(Dispatchers.IO)

    fun notifications(): Flow<ApiResult<List<NotificationDto>>> = flow {
        emit(ApiResult.Loading)
        try {
            val res = apiProvider.service().notifications()
            if (res.isSuccessful) emit(ApiResult.Success(res.body().orEmpty()))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load notifications."))
        }
    }.flowOn(Dispatchers.IO)

    fun unreadCount(): Flow<ApiResult<Int>> = flow {
        try {
            val res = apiProvider.service().unreadCount()
            if (res.isSuccessful) emit(ApiResult.Success(res.body()?.get("unread") ?: 0))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not load unread count."))
        }
    }.flowOn(Dispatchers.IO)

    fun markNotificationRead(id: String): Flow<ApiResult<Unit>> = flow {
        try {
            val res = apiProvider.service().markNotificationRead(id)
            if (res.isSuccessful) emit(ApiResult.Success(Unit))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not update notification."))
        }
    }.flowOn(Dispatchers.IO)

    fun markAllNotificationsRead(): Flow<ApiResult<Unit>> = flow {
        try {
            val res = apiProvider.service().markAllNotificationsRead()
            if (res.isSuccessful) emit(ApiResult.Success(Unit))
            else emit(ApiResult.Error(parseError(res)))
        } catch (e: IOException) {
            emit(ApiResult.Error(networkError(e)))
        } catch (_: Exception) {
            emit(ApiResult.Error("Could not update notifications."))
        }
    }.flowOn(Dispatchers.IO)

    fun activityLogs(accountId: String?, page: Int): Flow<ApiResult<PageResponse<ActivityLogDto>>> =
        flow {
            emit(ApiResult.Loading)
            try {
                val res = apiProvider.service().activityLogs(accountId, page, Constants.PAGE_SIZE)
                if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
                else emit(ApiResult.Error(parseError(res)))
            } catch (e: IOException) {
                emit(ApiResult.Error(networkError(e)))
            } catch (_: Exception) {
                emit(ApiResult.Error("Could not load activity logs."))
            }
        }.flowOn(Dispatchers.IO)

    fun errorLogs(accountId: String?, page: Int): Flow<ApiResult<PageResponse<ErrorLogDto>>> =
        flow {
            emit(ApiResult.Loading)
            try {
                val res = apiProvider.service().errorLogs(accountId, page, Constants.PAGE_SIZE)
                if (res.isSuccessful) emit(ApiResult.Success(res.body()!!))
                else emit(ApiResult.Error(parseError(res)))
            } catch (e: IOException) {
                emit(ApiResult.Error(networkError(e)))
            } catch (_: Exception) {
                emit(ApiResult.Error("Could not load error logs."))
            }
        }.flowOn(Dispatchers.IO)
}
