# TouchStation Extra — 20 game-error UX fixes

This update hardens the in-game fatal-error notice and adds swipe-up dismissal. It does not suppress the underlying error or claim to repair the native failure.

1. **first non-empty line** — ignore empty leading lines and show only the first usable error line.
2. **trimmed preview** — trim leading/trailing whitespace and collapse repeated spaces.
3. **control-character filtering** — remove unsafe control characters while preserving tabs.
4. **240-character display cap** — bound the visible preview so a native message cannot fill the screen.
5. **blank-message rejection** — reject blank messages instead of showing an empty banner.
6. **duplicate-message coalescing** — ignore repeated copies of the same visible error.
7. **one sound per visible incident** — play the notification sound only when a new notice first appears.
8. **replacement without repeated sound** — replace a visible error without replaying the notification sound.
9. **XMB error-dialog routing** — preserve the upstream XMB error-dialog route.
10. **safe XMB-state lookup** — read XMB state defensively so a failed UI-state read does not block the notice.
11. **safe notification sound** — guard sound playback so an audio/UI exception cannot discard the error notice.
12. **nonblank-only visibility** — show the banner only when a nonblank message exists.
13. **message-keyed gesture lifecycle** — key gesture handling to the current error so replacement resets the gesture state.
14. **vertical swipe recognition** — recognise vertical drag gestures on the banner.
15. **56 dp upward threshold** — require a deliberate upward swipe before dismissal.
16. **downward-swipe preservation** — keep downward swipes from dismissing the error.
17. **horizontal-gesture preservation** — leave horizontal gestures to the surrounding interface.
18. **cancelled-gesture reset** — reset gesture accumulation after cancellation or completion.
19. **accessible tap dismissal** — preserve tap-to-dismiss and expose an accessibility action label.
20. **upward animated dismissal** — fade and slide the notice upward; retain its text until the exit animation completes.

The existing banner remains bounded by safe drawing insets and a maximum width. These are Android UI and error-reporting improvements: a dismissed banner does not clear logs, fix a PPU/SPU/RSX error, or resume a stopped game.