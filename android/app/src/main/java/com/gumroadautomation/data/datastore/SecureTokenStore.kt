package com.gumroadautomation.data.datastore

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.gumroadautomation.util.Constants
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Auth tokens encrypted at rest with AES-256-GCM via AndroidX Security.
 * Synchronous API on purpose: OkHttp interceptors/authenticators run on
 * background threads and cannot call suspend functions directly.
 */
@Singleton
class SecureTokenStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val masterKey: MasterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        Constants.SECURE_PREFS_NAME,
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.ValueEncryptionScheme.AES256_GCM,
    )

    fun getAccessToken(): String? = prefs.getString(Constants.KEY_ACCESS_TOKEN, null)

    fun getRefreshToken(): String? = prefs.getString(Constants.KEY_REFRESH_TOKEN, null)

    fun hasTokens(): Boolean = !getAccessToken().isNullOrBlank()

    fun saveTokens(accessToken: String, refreshToken: String) {
        prefs.edit()
            .putString(Constants.KEY_ACCESS_TOKEN, accessToken)
            .putString(Constants.KEY_REFRESH_TOKEN, refreshToken)
            .apply()
    }

    /** Secure logout: wipe both tokens. Never log token values. */
    fun clear() {
        prefs.edit().clear().apply()
    }
}
