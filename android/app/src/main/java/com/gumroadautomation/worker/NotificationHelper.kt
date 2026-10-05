package com.gumroadautomation.worker

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.gumroadautomation.data.api.dto.DashboardDto
import com.gumroadautomation.util.Constants
import com.gumroadautomation.util.Money
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NotificationHelper @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    fun ensureChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                Constants.NOTIFICATION_CHANNEL_SYNC,
                "Sync updates",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply { description = "Background sync results and account alerts" }
            context.getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
        }
    }

    fun showSyncSummary(syncedAccounts: Int, dashboard: DashboardDto?) {
        ensureChannel()
        val revenue = dashboard?.let { Money.format(it.revenueCents, "USD") } ?: "—"
        val text = if (syncedAccounts == 0) {
            "No connected accounts to sync."
        } else {
            "$syncedAccounts account(s) synced • ${dashboard?.salesCount ?: 0} sales • $revenue revenue"
        }
        val notification = NotificationCompat.Builder(context, Constants.NOTIFICATION_CHANNEL_SYNC)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("Gumroad sync complete")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(SYNC_NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted — sync still succeeded; nothing to show.
        }
    }

    fun showReconnectNeeded(accountName: String) {
        ensureChannel()
        val notification = NotificationCompat.Builder(context, Constants.NOTIFICATION_CHANNEL_SYNC)
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            .setContentTitle("Gumroad account needs reconnect")
            .setContentText("$accountName returned 401. Open the app to reconnect.")
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(RECONNECT_NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
        }
    }

    companion object {
        private const val SYNC_NOTIFICATION_ID = 1001
        private const val RECONNECT_NOTIFICATION_ID = 1002
    }
}
