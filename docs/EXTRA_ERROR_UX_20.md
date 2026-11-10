# TouchStation Extra — 20 game-error UX fixes

This update hardens the in-game fatal-error notice and adds swipe-up dismissal. It does not suppress the underlying error or claim to repair the native failure.

1. Show only the first non-empty error line.
2. Trim leading and trailing whitespace.
3. Remove unsafe control characters while preserving tabs.
4. Limit the displayed error preview to 240 characters.
5. Reject blank messages instead of showing an empty banner.
6. Coalesce repeated identical messages.
7. Play the notification sound only when a new notice first appears.
8. Replace a visible error without replaying the notification sound.
9. Preserve the upstream XMB error-dialog route.
10. Read XMB state defensively so a failed UI-state read does not block the notice.
11. Guard notification playback so an audio/UI exception cannot discard the error notice.
12. Show the banner only when a nonblank message exists.
13. Key gesture handling to the current error so a replacement message resets the gesture state.
14. Recognise vertical drag gestures on the banner.
15. Require a deliberate 56 dp upward swipe before dismissal.
16. Keep downward swipes from dismissing the error.
17. Leave horizontal gestures to the surrounding interface.
18. Reset gesture accumulation after cancellation or completion.
19. Preserve tap-to-dismiss and expose an accessibility action label.
20. Fade and slide the notice upward when dismissed; retain its text until the exit animation completes.

The existing banner remains bounded by safe drawing insets and a maximum width. These are Android UI and error-reporting improvements: a dismissed banner does not clear logs, fix a PPU/SPU/RSX error, or resume a stopped game.