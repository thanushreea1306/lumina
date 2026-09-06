package com.lumina.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * JVM tests for [AudioMultipartBody] (CP-31).
 *
 * Verifies the multipart layout is deterministic, correctly calculates an
 * exact Content-Length, and can never smuggle a malicious filename into the
 * part headers (no CRLF, quotes, or path components).
 */
class AudioMultipartBodyTest {

    private val boundary = AudioMultipartBody.generateBoundary("abcdef1234567890")

    @Test
    fun `boundary is namespaced and deterministic from the nonce`() {
        assertEquals("----LuminaBoundary" + "abcdef1234567890", boundary)
        assertTrue(boundary.startsWith(AudioMultipartBody.BOUNDARY_PREFIX))
    }

    @Test
    fun `generateBoundary uses only the nonce prefix`() {
        // "--" + 4 more dashes already in prefix + "LuminaBoundary" (15) + 16 nonce chars.
        assertEquals(AudioMultipartBody.BOUNDARY_PREFIX.length + 16, boundary.length)
    }

    @Test
    fun `header carries the form field name file and boundary`() {
        val header = AudioMultipartBody.filePartHeader("clip.wav", "audio/wav", boundary)
        assertTrue(header.startsWith("--$boundary\r\n"))
        assertTrue(header.contains("name=\"file\""))
        assertTrue(header.contains("filename=\"clip.wav\""))
        assertTrue(header.contains("Content-Type: audio/wav"))
        assertTrue(header.endsWith("\r\n\r\n"))
    }

    @Test
    fun `closing boundary terminates the multipart body`() {
        assertEquals("\r\n--$boundary--\r\n", AudioMultipartBody.closingBoundary(boundary))
    }

    @Test
    fun `contentLength exactly sums header, payload and closing bytes`() {
        val header = AudioMultipartBody.filePartHeader("clip.wav", "audio/wav", boundary)
        val closing = AudioMultipartBody.closingBoundary(boundary)
        val headerBytes = AudioMultipartBody.utf8Length(header)
        val closingBytes = AudioMultipartBody.utf8Length(closing)

        // A small fake payload with a known length.
        val payload = "AUDIODATA".toByteArray(Charsets.UTF_8)
        val expectedTotal = headerBytes.toInt() + payload.size + closingBytes.toInt()

        assertEquals(
            expectedTotal.toLong(),
            AudioMultipartBody.contentLength(payload.size.toLong(), headerBytes, closingBytes),
        )
    }

    @Test
    fun `utf8Length counts bytes not characters`() {
        assertEquals(5, AudioMultipartBody.utf8Length("hello"))
        // "é" is 2 bytes in UTF-8, so "héllo" is 6 bytes.
        assertEquals(6, AudioMultipartBody.utf8Length("héllo"))
    }

    @Test
    fun `sanitizeFilename strips directory components`() {
        assertEquals("clip.wav", AudioMultipartBody.sanitizeFilename("/a/b/clip.wav"))
        assertEquals("clip.wav", AudioMultipartBody.sanitizeFilename("C:\\Temp\\clip.wav"))
    }

    @Test
    fun `sanitizeFilename neutralizes header injection`() {
        assertEquals("audio", AudioMultipartBody.sanitizeFilename("evil\"\"bounced.wav"))
        assertEquals("audio", AudioMultipartBody.sanitizeFilename("evil\r\nContent-Disposition: x.wav"))
        assertEquals("audio", AudioMultipartBody.sanitizeFilename(""))
        assertEquals("audio", AudioMultipartBody.sanitizeFilename("   "))
    }

    @Test
    fun `unsanitized injection would break the header but sanitize prevents it`() {
        val safe = AudioMultipartBody.sanitizeFilename("x\r\nInjected: header")
        val header = AudioMultipartBody.filePartHeader(safe, "audio/wav", boundary)
        assertFalse("no CRLF may survive in the header", header.contains("\r\nInjected"))
        val quoted = header.substringAfter("filename=\"").substringBeforeLast('"')
        assertFalse("no double quote inside the filename attribute except the delimiters",
            quoted.contains("\""))
    }

    @Test
    fun `multipart body bytes match the computed content length`() {
        val header = AudioMultipartBody.filePartHeader("clip.wav", "audio/wav", boundary)
        val closing = AudioMultipartBody.closingBoundary(boundary)
        val payload = ByteArray(10) { 0x41 }

        val totalBytes = header.toByteArray(Charsets.UTF_8).size +
            payload.size +
            closing.toByteArray(Charsets.UTF_8).size

        assertEquals(
            totalBytes.toLong(),
            AudioMultipartBody.contentLength(
                payload.size.toLong(),
                AudioMultipartBody.utf8Length(header),
                AudioMultipartBody.utf8Length(closing),
            ),
        )
    }
}