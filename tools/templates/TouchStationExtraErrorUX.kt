package com.armsx2.ui.emulation

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.armsx2.MenuSfx
import com.armsx2.i18n.str

private const val GAME_ERROR_NOTICE_MAX_CHARS = 240
private const val GAME_ERROR_DISMISS_THRESHOLD_DP = 56

/**
 * Displays the first useful line of a fatal game-thread error.
 * Error text is bounded and sanitised; repeated copies are coalesced while visible.
 */
object GameErrorNotice {
    /** The sanitised first line, or null while no notice is visible. */
    val reason = mutableStateOf<String?>(null)

    /** Called with the message returned by Rpcs3Bridge.takeGameError, on the main thread. */
    fun show(error: String) {
        val firstLine = error.lineSequence().firstOrNull { it.isNotBlank() } ?: return
        val cleaned = buildString(firstLine.length) {
            firstLine.forEach { char ->
                if (char == '\t' || !java.lang.Character.isISOControl(char)) append(char)
            }
        }.trim().replace(Regex("\\s+"), " ")
        if (cleaned.isBlank()) return

        val preview = if (cleaned.length > GAME_ERROR_NOTICE_MAX_CHARS) {
            cleaned.take(GAME_ERROR_NOTICE_MAX_CHARS - 1).trimEnd() + "…"
        } else cleaned

        val previous = reason.value
        if (previous == preview) return

        val wasVisible = !previous.isNullOrBlank()
        val xmbActive = runCatching {
            com.armsx2.ui.xmb.XmbMode.active.value
        }.getOrDefault(false)
        if (!wasVisible && !xmbActive) {
            runCatching { MenuSfx.play(MenuSfx.Event.POPUP_OPEN) }
        }
        reason.value = preview
    }

    fun clear() {
        if (reason.value != null) reason.value = null
    }
}

@Composable
fun GameErrorBanner() {
    val reason by GameErrorNotice.reason
    val xmbActive = runCatching {
        com.armsx2.ui.xmb.XmbMode.active.value
    }.getOrDefault(false)

    // XMB mode shows the console's own error dialog when it can handle the notice.
    if (xmbActive && runCatching {
            com.armsx2.ui.xmb.xmbGameError(reason)
        }.getOrDefault(false)
    ) return

    val hasReason = !reason.isNullOrBlank()
    val dismissThresholdPx = with(LocalDensity.current) {
        GAME_ERROR_DISMISS_THRESHOLD_DP.dp.toPx()
    }

    AnimatedVisibility(
        visible = hasReason,
        enter = fadeIn(tween(180)) + slideInVertically(tween(240)) { -it },
        // A swipe-up dismissal clears state; this exit animation carries the notice off-screen.
        exit = fadeOut(tween(160)) + slideOutVertically(tween(220)) { -it },
    ) {
        // Keep the outgoing copy alive until AnimatedVisibility completes its exit transition.
        val shown = remember(reason) { reason }.orEmpty()
        val what = if ("RPCN" in shown) str("game.error.rpcn") else str("game.error.other")

        Surface(
            modifier = Modifier
                .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top))
                .padding(horizontal = 14.dp, vertical = 10.dp)
                .widthIn(max = 560.dp)
                .pointerInput(reason) {
                    var totalVerticalDragPx = 0f
                    detectVerticalDragGestures(
                        onDragStart = { totalVerticalDragPx = 0f },
                        onVerticalDrag = { change, dragAmount ->
                            totalVerticalDragPx += dragAmount
                            change.consume()
                        },
                        onDragEnd = {
                            val dismiss = totalVerticalDragPx <= -dismissThresholdPx
                            totalVerticalDragPx = 0f
                            if (dismiss) GameErrorNotice.clear()
                        },
                        onDragCancel = { totalVerticalDragPx = 0f },
                    )
                }
                .clickable(
                    role = Role.Button,
                    onClickLabel = "Dismiss game error",
                ) { GameErrorNotice.clear() },
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surfaceVariant,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.8f)),
            shadowElevation = 14.dp,
        ) {
            Column(
                Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    str("game.error.title"),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.error,
                )
                Text(what, style = MaterialTheme.typography.bodyMedium)
                Text(
                    shown,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    "Swipe up or tap to dismiss",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
