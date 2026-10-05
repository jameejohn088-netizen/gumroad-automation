package com.gumroadautomation.data.api

import com.gumroadautomation.data.datastore.SecureTokenStore
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Adds `Authorization: Bearer <access_token>` to backend calls.
 * Auth endpoints (login/signup/refresh/...) are skipped — they carry no token yet,
 * or (refresh) must not send the stale access token.
 */
@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenStore: SecureTokenStore,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val path = request.url.encodedPath
        val isAuthCall = path.contains("/auth/login") ||
            path.contains("/auth/signup") ||
            path.contains("/auth/refresh") ||
            path.contains("/auth/forgot-password") ||
            path.contains("/auth/reset-password") ||
            path.contains("/auth/verify-email")
        if (isAuthCall) return chain.proceed(request)

        val token = tokenStore.getAccessToken()
        if (token.isNullOrBlank()) return chain.proceed(request)

        // Redaction: the token value is never logged (see logging interceptor config).
        val authed = request.newBuilder()
            .header("Authorization", "Bearer $token")
            .build()
        return chain.proceed(authed)
    }
}

/**
 * One-shot event bus so the [TokenAuthenticator] (which cannot inject repositories
 * without creating a dependency cycle) can tell the UI that the session is dead.
 */
@Singleton
class AuthEventBus @Inject constructor() {
    private val _unauthorized = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val unauthorized: SharedFlow<Unit> = _unauthorized.asSharedFlow()

    fun emitUnauthorized() {
        _unauthorized.tryEmit(Unit)
    }
}
