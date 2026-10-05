package com.gumroadautomation.worker

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.gumroadautomation.data.api.ApiProvider
import com.gumroadautomation.data.datastore.SecureTokenStore
import com.gumroadautomation.util.Constants
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.io.IOException

/**
 * Periodic background sync.
 *
 * HONEST LIMITATIONS (also documented in-app under Settings → About sync):
 * - WorkManager enforces a **minimum 15-minute interval** for periodic work.
 * - The OS may delay, batch, or skip runs (Doze mode, battery optimizations,
 *   manufacturer-specific restrictions). Background execution is best-effort.
 * - True 24/7 automation while the phone is offline requires a continuously
 *   running server — the Android app cannot guarantee that.
 *
 * The worker only *triggers* server-side sync jobs and reads back aggregates;
 * all Gumroad API calls happen on the backend, never on the device.
 */
@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val apiProvider: ApiProvider,
    private val tokenStore: SecureTokenStore,
    private val notificationHelper: NotificationHelper,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        if (!tokenStore.hasTokens()) {
            // Logged out — nothing to sync. Cancel future runs via logout flow.
            return Result.success()
        }
        return try {
            val api = apiProvider.service()
            val accounts = api.listAccounts().body().orEmpty()
            val connected = accounts.filter { it.status == Constants.STATUS_CONNECTED }
            var synced = 0
            for (account in connected) {
                try {
                    val res = api.syncAccount(account.id)
                    if (res.isSuccessful) synced++
                } catch (_: Exception) {
                    // One account failing must not abort the others.
                }
            }
            val needsReconnect = accounts.filter {
                it.status == Constants.STATUS_NEEDS_RECONNECT || it.status == Constants.STATUS_ERROR
            }
            for (account in needsReconnect) {
                notificationHelper.showReconnectNeeded(account.name)
            }
            val dashboard = try {
                api.dashboard(null).body()
            } catch (_: Exception) {
                null
            }
            notificationHelper.showSyncSummary(synced, dashboard)
            Result.success()
        } catch (e: IOException) {
            // Transient network failure — let WorkManager retry with backoff.
            Result.retry()
        } catch (_: Exception) {
            Result.failure()
        }
    }
}
