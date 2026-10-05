package com.gumroadautomation

import com.gumroadautomation.util.ApiResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiResultTest {

    @Test
    fun `success carries data`() {
        val result: ApiResult<String> = ApiResult.Success("ok")
        assertTrue(result is ApiResult.Success)
        assertEquals("ok", (result as ApiResult.Success).data)
    }

    @Test
    fun `error can carry cached data`() {
        val cached = listOf("stale")
        val result: ApiResult<List<String>> = ApiResult.Error("offline", cached)
        assertTrue(result is ApiResult.Error)
        assertEquals(cached, (result as ApiResult.Error).cached)
    }

    @Test
    fun `loading is a singleton`() {
        val a: ApiResult<Int> = ApiResult.Loading
        val b: ApiResult<String> = ApiResult.Loading
        assertTrue(a === b)
    }
}
