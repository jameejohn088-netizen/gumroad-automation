package com.gumroadautomation.util

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Best-effort ISO-8601 date formatting; never throws for UI code paths. */
object DateUtils {

    private val dateFormatter =
        DateTimeFormatter.ofPattern("MMM d, yyyy", Locale.US).withZone(ZoneId.systemDefault())
    private val dateTimeFormatter =
        DateTimeFormatter.ofPattern("MMM d, yyyy HH:mm", Locale.US).withZone(ZoneId.systemDefault())

    fun formatDate(iso: String?): String = formatWith(iso, dateFormatter)

    fun formatDateTime(iso: String?): String = formatWith(iso, dateTimeFormatter)

    private fun formatWith(iso: String?, formatter: DateTimeFormatter): String {
        if (iso.isNullOrBlank()) return "—"
        return try {
            formatter.format(Instant.parse(iso))
        } catch (_: Exception) {
            // Fall back to date-only prefix of the raw string.
            iso.take(10)
        }
    }
}
