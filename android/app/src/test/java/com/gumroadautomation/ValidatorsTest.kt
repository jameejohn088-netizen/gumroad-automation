package com.gumroadautomation

import com.gumroadautomation.util.Validators
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ValidatorsTest {

    @Test
    fun `valid email passes`() {
        assertNull(Validators.emailError("anna@example.com"))
    }

    @Test
    fun `blank email fails`() {
        assertEquals("Email is required", Validators.emailError(""))
    }

    @Test
    fun `malformed email fails`() {
        assertEquals("Enter a valid email address", Validators.emailError("not-an-email"))
    }

    @Test
    fun `short password fails`() {
        assertEquals(
            "Password must be at least 8 characters",
            Validators.passwordError("short"),
        )
    }

    @Test
    fun `valid password passes`() {
        assertNull(Validators.passwordError("long-enough-password"))
    }

    @Test
    fun `base url requires scheme`() {
        assertEquals(
            "URL must start with http:// or https://",
            Validators.baseUrlError("192.168.1.10:8000"),
        )
    }

    @Test
    fun `base url normalizes bare host`() {
        assertEquals(
            "http://192.168.1.10:8000/api/v1",
            Validators.normalizeBaseUrl("http://192.168.1.10:8000"),
        )
    }

    @Test
    fun `base url keeps existing api prefix`() {
        assertEquals(
            "http://10.0.2.2:8000/api/v1",
            Validators.normalizeBaseUrl("http://10.0.2.2:8000/api/v1/"),
        )
    }
}
