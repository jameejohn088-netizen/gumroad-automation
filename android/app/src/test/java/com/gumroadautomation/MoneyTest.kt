package com.gumroadautomation

import com.gumroadautomation.util.Money
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MoneyTest {

    @Test
    fun `formats USD cents`() {
        assertEquals("$19.99", Money.format(1999L, "usd"))
    }

    @Test
    fun `formats zero`() {
        assertEquals("$0.00", Money.format(0L, "USD"))
    }

    @Test
    fun `falls back gracefully for unknown currency`() {
        val result = Money.format(100L, "XYZ")
        assertTrue(result.contains("1.00"))
    }

    @Test
    fun `handles null currency as USD`() {
        assertEquals("$5.00", Money.format(500, null))
    }
}
