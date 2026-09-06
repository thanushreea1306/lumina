package com.lumina.app

/**
 * Deterministic multipart/form-data layout for the audio evidence upload.
 *
 * The backend consumes a standard `UploadFile` field named `file`. The whole
 * body layout is computed here so that:
 *   - the exact Content-Length is known before streaming (no chunked surprises)
 *   - the filename is sanitized so it can never smuggle CRLF/quotes into the
 *     multipart boundary or headers
 *   - the layout is JVM-testable without a device or network
 *
 * Audio bytes are never loaded into memory: the upload streams the temp file
 * between [filePartHeader] and [closingBoundary].
 */
object AudioMultipartBody {

    const val FIELD_NAME = "file"
    const val BOUNDARY_PREFIX = "----LuminaBoundary"

    /** Build a unique multipart boundary; only deterministic via a caller nonce. */
    fun generateBoundary(nonceHex: String): String =
        BOUNDARY_PREFIX + (nonceHex.take(16))

    /**
     * Sanitize a user-supplied filename for use inside a multipart part.
     * Strips any path components and header-injection characters (CR/LF and
     * double quotes are rejected, not escaped, so the Content-Length contract
     * stays exact).
     */
    fun sanitizeFilename(original: String): String {
        var name = original.substringAfterLast('/').substringAfterLast('\\').trim()
        if (name.isEmpty()) return "audio"
        if (name.any { it == '\r' || it == '\n' || it == '"' }) return "audio"
        return name
    }

    /**
     * The head of the file part including the opening boundary.
     * CRLF line endings per RFC 2046.
     */
    fun filePartHeader(filename: String, contentType: String, boundary: String): String {
        val safeName = sanitizeFilename(filename)
        return "--$boundary\r\n" +
            "Content-Disposition: form-data; name=\"$FIELD_NAME\"; filename=\"$safeName\"\r\n" +
            "Content-Type: $contentType\r\n" +
            "\r\n"
    }

    /** The closing delimiter that terminates the multipart body. */
    fun closingBoundary(boundary: String): String = "\r\n--$boundary--\r\n"

    /** Exact byte length of the full multipart body for a file of [fileSizeBytes]. */
    fun contentLength(fileSizeBytes: Long, headerBytes: Long, closingBytes: Long): Long =
        headerBytes + fileSizeBytes + closingBytes

    /** Byte length of a header/closing string encoded as UTF-8. */
    fun utf8Length(text: String): Long = text.toByteArray(Charsets.UTF_8).size.toLong()
}