package com.gumroadautomation.data.datastore

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.gumroadautomation.util.Constants
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = Constants.PREFS_DATASTORE_NAME
)

/**
 * Non-sensitive app preferences (DataStore). Tokens are NOT stored here —
 * see [SecureTokenStore] (EncryptedSharedPreferences).
 */
@Singleton
class SessionManager @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private val baseUrlKey = stringPreferencesKey(Constants.KEY_BASE_URL)
    private val selectedAccountKey = stringPreferencesKey(Constants.KEY_SELECTED_ACCOUNT_ID)
    private val themeModeKey = stringPreferencesKey(Constants.KEY_THEME_MODE)
    private val syncEnabledKey = booleanPreferencesKey(Constants.KEY_SYNC_ENABLED)

    /** null = "All Accounts" view. */
    val selectedAccountId: Flow<String?> = context.settingsDataStore.data
        .map { it[selectedAccountKey] }

    val baseUrl: Flow<String> = context.settingsDataStore.data
        .map { it[baseUrlKey] ?: Constants.DEFAULT_BASE_URL }

    /** system | light | dark */
    val themeMode: Flow<String> = context.settingsDataStore.data
        .map { it[themeModeKey] ?: "system" }

    val syncEnabled: Flow<Boolean> = context.settingsDataStore.data
        .map { it[syncEnabledKey] ?: true }

    suspend fun setSelectedAccountId(accountId: String?) {
        context.settingsDataStore.edit { prefs ->
            if (accountId == null) prefs.remove(selectedAccountKey)
            else prefs[selectedAccountKey] = accountId
        }
    }

    suspend fun setBaseUrl(url: String) {
        context.settingsDataStore.edit { it[baseUrlKey] = url }
    }

    suspend fun setThemeMode(mode: String) {
        context.settingsDataStore.edit { it[themeModeKey] = mode }
    }

    suspend fun setSyncEnabled(enabled: Boolean) {
        context.settingsDataStore.edit { it[syncEnabledKey] = enabled }
    }
}
