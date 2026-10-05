package com.gumroadautomation.util

/**
 * Standard UI result wrapper. [cached] may carry stale offline data alongside an error
 * so screens can show "offline — showing cached data" instead of a blank error.
 */
sealed interface ApiResult<out T> {
    data object Loading : ApiResult<Nothing>
    data class Success<T>(val data: T) : ApiResult<T>
    data class Error(val message: String, val cached: Any? = null) : ApiResult<Nothing>
}
