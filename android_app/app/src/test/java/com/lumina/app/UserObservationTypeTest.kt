package com.lumina.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Tests for [UserObservationType] enum: verifies all types are present,
 * labels are non-empty, and the enum aligns with the Phase 3 backend.
 */
class UserObservationTypeTest {

    @Test
    fun `all 16 observation types are defined`() {
        assertEquals(16, UserObservationType.values().size)
    }

    @Test
    fun `every type has a non-empty label`() {
        for (type in UserObservationType.values()) {
            assertTrue("${type.name} has empty label", type.label.isNotEmpty())
        }
    }

    @Test
    fun `every type has a non-empty description`() {
        for (type in UserObservationType.values()) {
            assertTrue("${type.name} has empty description", type.description.isNotEmpty())
        }
    }

    @Test
    fun `coercion types include authority claim and threats`() {
        assertTrue(UserObservationType.COERCION_TYPES.contains(UserObservationType.AUTHORITY_CLAIM))
        assertTrue(UserObservationType.COERCION_TYPES.contains(UserObservationType.THREAT_OF_ARREST))
        assertTrue(UserObservationType.COERCION_TYPES.contains(UserObservationType.THREAT_OF_LEGAL_ACTION))
    }

    @Test
    fun `sensitive request types include money and OTP`() {
        assertTrue(UserObservationType.SENSITIVE_REQUEST_TYPES.contains(UserObservationType.MONEY_REQUEST))
        assertTrue(UserObservationType.SENSITIVE_REQUEST_TYPES.contains(UserObservationType.OTP_REQUEST))
        assertTrue(UserObservationType.SENSITIVE_REQUEST_TYPES.contains(UserObservationType.PASSWORD_REQUEST))
    }

    @Test
    fun `valueOf matches backend observation type names`() {
        // These must match the Python enum values in app/evidence/models.py
        val expectedBackendNames = setOf(
            "AUTHORITY_CLAIM",
            "THREAT_OF_ARREST",
            "THREAT_OF_LEGAL_ACTION",
            "URGENCY",
            "SECRECY_REQUEST",
            "MONEY_REQUEST",
            "OTP_REQUEST",
            "PASSWORD_REQUEST",
            "IDENTITY_DOCUMENT_REQUEST",
            "REMOTE_ACCESS_REQUEST",
            "APP_INSTALL_REQUEST",
            "BANK_TRANSFER_REQUEST",
            "CRYPTO_REQUEST",
            "GIFT_CARD_REQUEST",
            "CALL_BACK_INSTRUCTION",
            "INDEPENDENT_VERIFICATION_BLOCKED",
        )
        val androidNames = UserObservationType.values().map { it.name }.toSet()
        assertEquals(expectedBackendNames, androidNames)
    }

    @Test
    fun `type names can be used as backend request values`() {
        for (type in UserObservationType.values()) {
            assertNotNull("Type name should be valid: ${type.name}", type.name)
            assertTrue("Type name should be uppercase: ${type.name}", type.name == type.name.uppercase())
        }
    }
}
