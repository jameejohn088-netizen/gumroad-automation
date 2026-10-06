package com.gumroadautomation.util

import java.text.NumberFormat
import java.util.Currency
import java.util.Locale

/** Money formatting helpers. Amounts from the API are in minor units (cents). */
object Money {

    /**
     * Formats [cents] in [currencyCode] for display, e.g. 1999 + "usd" -> "$19.99".
     * Falls back to a plain "19.99 USD" style string for unknown currencies.
     */
    fun format(cents: Long, currencyCode: String?): String {
        val code = currencyCode?.uppercase(Locale.US).orEmpty()
        val amount = cents / 100.0
        return try {
            val currency = Currency.getInstance(code.ifEmpty { "USD" })
            val nf = NumberFormat.getCurrencyInstance(Locale.US).apply { this.currency = currency }
            nf.format(amount)
        } catch (_: IllegalArgumentException) {
            "%.2f %s".format(Locale.US, amount, code.ifEmpty { "USD" })
        }
    }

    fun format(cents: Int, currencyCode: String?): String = format(cents.toLong(), currencyCode)
}
