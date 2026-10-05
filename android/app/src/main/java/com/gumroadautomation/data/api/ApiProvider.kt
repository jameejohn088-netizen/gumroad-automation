package com.gumroadautomation.data.api

import com.google.gson.Gson
import com.gumroadautomation.data.datastore.SessionManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.ConcurrentHashMap
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Builds [ApiService] instances for the currently configured backend base URL.
 *
 * The base URL is user-configurable (Settings → Backend URL), so Retrofit cannot be
 * a fixed singleton: instances are cached per normalized base URL instead.
 */
@Singleton
class ApiProvider @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val gson: Gson,
    private val sessionManager: SessionManager,
) {
    private val cache = ConcurrentHashMap<String, ApiService>()

    /** Returns the service for the saved base URL. Call from a background thread. */
    fun service(): ApiService {
        val baseUrl = runBlocking { sessionManager.baseUrl.first() }
        return serviceFor(baseUrl)
    }

    fun serviceFor(baseUrl: String): ApiService {
        val normalized = baseUrl.trim().removeSuffix("/")
        return cache.getOrPut(normalized) {
            Retrofit.Builder()
                .baseUrl("$normalized/")
                .client(okHttpClient)
                .addConverterFactory(GsonConverterFactory.create(gson))
                .build()
                .create(ApiService::class.java)
        }
    }

    /** Drop cached instances after the base URL changes. */
    fun invalidate() {
        cache.clear()
    }
}
