# Original User Request

## 2026-09-11T06:42:50Z

This is a single self-contained fix; keep it small and focused.
Fix the Scopa gameplay focus and accessibility audio issues without touching any code outside the Scopa scope.

Working directory: C:\Users\midoa\Downloads\letsfly_full_source_both\Windows
Integrity mode: development

## Requirements

### R1. Fix Focus Escaping to Chat
When playing cards in Scopa, focus must remain firmly on the Scopa card list during the player's turn. Removing played cards or updating items must never allow Qt focus to escape to chat_input or general table widgets.

### R2. Prevent Redundant List / قائمة Announcements on Every Card
Screen readers (NVDA) must not announce قائمة / List or re-read the entire card list when an opponent plays a card or when an in-hand card is played. Only the actual action or the new active turn should be announced.

### R3. Complete Last Card & Capture Announcements and Sounds
When the final card of a deal or round is played:
- The card throw sound (SCOPA_CARD_THROW) and any capture sound (SCOPA_EAT_CARDS / SCOPA_SWEEP) must play reliably.
- The capture text must be announced by the screen reader and must not be cut off or swallowed by the round summary or next batch deal.
- Server state finalization must not overwrite or drop the final card's action event before the client receives and plays it.

### R4. Strict Scope Boundary
Do not touch or modify any code, logic, or files unrelated to Scopa.

## Acceptance Criteria

### Focus & Accessibility
- [ ] During active gameplay on the player's turn, navigating or playing cards never shifts focus to chat_input.
- [ ] NVDA does not announce قائمة / List when cards are played by opponents or after the player plays a card in hand.
- [ ] When playing the last card of a batch/round with a capture, the throw sound and capture sound play audibly.
- [ ] The speech synthesizer announces the last play and capture text completely without interruption.
- [ ] Code changes are strictly isolated to Scopa-relevant client and server logic.
