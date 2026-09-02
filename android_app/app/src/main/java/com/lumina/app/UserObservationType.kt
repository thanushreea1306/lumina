package com.lumina.app

/**
 * Observation types matching the Phase 3 backend [UserObservationType] enum.
 *
 * These are categories the user can voluntarily report about a call.
 * Each becomes evidence only when the user explicitly selects it
 * (source=USER, status=USER_CONFIRMED). The system NEVER infers
 * these from device signals.
 *
 * Labels are human-readable for the observation UI.
 */
enum class UserObservationType(val label: String, val description: String) {
    AUTHORITY_CLAIM(
        "Authority claim",
        "Caller claimed to be from police, bank, government, or another authority"
    ),
    THREAT_OF_ARREST(
        "Threat of arrest",
        "Caller threatened that you or someone will be arrested"
    ),
    THREAT_OF_LEGAL_ACTION(
        "Threat of legal action",
        "Caller threatened legal consequences or court action"
    ),
    URGENCY(
        "Urgency pressure",
        "Caller pressured you to act immediately without time to think"
    ),
    SECRECY_REQUEST(
        "Secrecy request",
        "Caller asked you to keep the matter secret from family or others"
    ),
    MONEY_REQUEST(
        "Money request",
        "Caller asked you to send, transfer, or pay money"
    ),
    OTP_REQUEST(
        "OTP / code request",
        "Caller asked for a one-time password, verification code, or PIN"
    ),
    PASSWORD_REQUEST(
        "Password request",
        "Caller asked for your password or login credentials"
    ),
    IDENTITY_DOCUMENT_REQUEST(
        "ID document request",
        "Caller asked for a copy of your ID, passport, or other documents"
    ),
    REMOTE_ACCESS_REQUEST(
        "Remote access request",
        "Caller asked you to install an app or grant remote access to your device"
    ),
    APP_INSTALL_REQUEST(
        "App install request",
        "Caller asked you to download or install a specific application"
    ),
    BANK_TRANSFER_REQUEST(
        "Bank transfer request",
        "Caller asked you to make a bank transfer or wire payment"
    ),
    CRYPTO_REQUEST(
        "Crypto transfer request",
        "Caller asked you to transfer cryptocurrency"
    ),
    GIFT_CARD_REQUEST(
        "Gift card request",
        "Caller asked you to purchase gift cards"
    ),
    CALL_BACK_INSTRUCTION(
        "Call-back instruction",
        "Caller told you to call a specific number back"
    ),
    INDEPENDENT_VERIFICATION_BLOCKED(
        "Verification blocked",
        "Caller prevented or discouraged you from verifying their identity independently"
    );

    companion object {
        /**
         * All types that represent coercion or authority impersonation.
         * Used for display grouping.
         */
        val COERCION_TYPES = setOf(AUTHORITY_CLAIM, THREAT_OF_ARREST, THREAT_OF_LEGAL_ACTION)

        /**
         * Types that represent requests for sensitive information or money.
         */
        val SENSITIVE_REQUEST_TYPES = setOf(
            OTP_REQUEST, PASSWORD_REQUEST, MONEY_REQUEST, BANK_TRANSFER_REQUEST,
            CRYPTO_REQUEST, GIFT_CARD_REQUEST, IDENTITY_DOCUMENT_REQUEST,
        )
    }
}
