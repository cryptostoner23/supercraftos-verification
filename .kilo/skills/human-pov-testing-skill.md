# Human POV Testing Skill — Real-Device E2E Testing

## Philosophy

**Test exactly like a human user would.** No terminal commands, no backend API calls, no shell scripts, no developer tools. Every interaction must go through the app's user-facing interface on a real physical device or device session.

The goal: validate that a real person can install, launch, and use SuperCraftOS without any technical knowledge, encountering zero crashes, zero broken flows, and zero missing features. Minimum quality threshold: **9.5/10** — no cheating, no compromise, no skipped steps.

## What "Human POV" Means

| Human Action | Allowed | Not Allowed |
|--------------|---------|-------------|
| Tap a button on screen | ✅ | Running `curl` against an API |
| Type text in a field | ✅ | Editing `Info.plist` or `project.yml` |
| Swipe between screens | ✅ | Using Xcode debugger or LLDB |
| Read error messages | ✅ | Checking server logs |
| Wait for loading states | ✅ | Using `bitrise build log` CLI |
| Restart the app | ✅ | Modifying source code mid-test |
| Reinstall the app | ✅ | Using terminal/SSH to device |

## Test Methodology

### Phase 1: Installation (Human Only)

1. Obtain the `.ipa` from Bitrise build output or Revyl build registration
2. Install via AltStore, SideStore, TestFlight, or direct sideload — **exactly as a user would**
3. Launch the app from the home screen
4. Verify: app icon appears, app opens without crash, splash/launch screen displays

### Phase 2: Core User Journeys (18 Tests)

Each journey below must be completed **end-to-end through the UI only**:

#### 1. Fresh IPA Installation and Launch
- Install app, tap icon, verify launch, verify home/dashboard loads
- **Pass criteria**: App opens in <5 seconds, no crash, no blank screen

#### 2. Onboarding and Identity Configuration
- Complete all onboarding screens, set user preferences, save identity
- **Pass criteria**: Onboarding completes, preferences persist, profile accessible

#### 3. Memory Creation and Retrieval
- Create memory entry with text, save, navigate to list, verify entry appears, open entry, verify content
- **Pass criteria**: Memory saved and retrievable, content matches exactly

#### 4. Context-Aware AI Conversations
- Start conversation, send context-referencing message, verify AI responds with context
- **Pass criteria**: AI response references previous context, conversation history preserved

#### 5. Project and Task Creation
- Create project, create task within project, assign to agent
- **Pass criteria**: Project and task visible in project list, assignment confirmed

#### 6. Agent Delegation
- Select task, choose agent, confirm delegation
- **Pass criteria**: Agent status shows delegated task, acceptance confirmed

#### 7. Multi-Agent Execution
- Create workflow requiring multiple agents, assign agents, execute
- **Pass criteria**: All agents complete steps, workflow marked complete

#### 8. Workflow Creation and Execution
- Create workflow with steps, configure dependencies, execute
- **Pass criteria**: Workflow executes successfully, all steps complete

#### 9. Document Ingestion and Retrieval
- Upload document, verify indexing, search for content, verify result
- **Pass criteria**: Document processed, searchable, content retrievable

#### 10. Artifact Generation
- Configure parameters, generate artifact, verify creation, open/export
- **Pass criteria**: Artifact generated, accessible, exportable

#### 11. Integration Connection and Execution
- Connect external integration, authenticate, execute action
- **Pass criteria**: Integration connected, action completes successfully

#### 12. Model Switching and Fallback
- Switch AI provider/model, send query, verify switch, test fallback
- **Pass criteria**: Model switch effective, fallback works when primary unavailable

#### 13. AI Keyboard Usage
- Open text field, activate keyboard, generate suggestions, insert text
- **Pass criteria**: Keyboard works in all text fields, suggestions accurate

#### 14. Data Persistence After App Termination
- Create data, force-quit app, relaunch, verify data intact
- **Pass criteria**: Data survives app termination, no corruption

#### 15. Memory Modification and Deletion
- Edit memory, save, verify changes; delete memory, verify removal
- **Pass criteria**: Edits saved, deletions reflected in list

#### 16. Network Interruption and Recovery
- Start operation, disconnect network, verify graceful handling, reconnect, verify recovery
- **Pass criteria**: App handles disconnect without crash, recovers on reconnect

#### 17. Authentication and Permissions
- Login/logout, grant permissions, verify authenticated API calls
- **Pass criteria**: Auth flow works, permissions respected, API calls succeed

#### 18. Application Background/Foreground Transitions
- Start activity, background app, wait, return to foreground, verify state preserved
- **Pass criteria**: App state preserved across backgrounding, activity resumes

#### 19. Failure Handling and Recovery
- Trigger failure, verify error message, recover, verify usable state
- **Pass criteria**: App shows error, recovers gracefully, no data corruption

#### 20. Full Application Regression
- Navigate all features, verify keyboard extension, verify persistence, verify APIs
- **Pass criteria**: Zero crashes, zero critical bugs across all features

## Device Requirements

| Requirement | Specification |
|-------------|---------------|
| Physical device | iPhone or iPad (real hardware, not simulator only) |
| iOS version | iOS 17+ minimum |
| Storage | Sufficient free space for app + data |
| Network | Wi-Fi or cellular for API-dependent features |
| Display | Multiple screen sizes if possible (iPhone SE, iPhone 15/16, iPad) |
| Orientation | Portrait and landscape testing |

## Revyl Device Session Setup

```bash
# Start a device session for human POV testing
/revyl device start --platform ios --app-id 017e6103-7dbe-4ba3-a910-88575e966048 \
  --build-version-id 834300f6-ff12-4a10-bf70-84eba1392252

# Interact with the device through Revyl's device session UI
# (accessible via https://app.revyl.ai)

# Stop session when done
/revyl device stop <session-id>
```

## Evidence Collection (Human POV)

For every test, capture:

1. **Device model and iOS version** (e.g., iPhone 15 Pro, iOS 17.6)
2. **Screenshots** of every screen visited
3. **Screen recording** of the complete user journey
4. **Timestamps** for each step start/completion
5. **Error messages** exactly as displayed to the user
6. **Load times** measured with a stopwatch
7. **Pass/fail verdict** per test

## Quality Threshold: 9.5/10

A test passes only if:

- ✅ App launches without crash (100% of attempts)
- ✅ Every button tap produces expected result
- ✅ No blank/white screens during normal operation
- ✅ All text is readable and correctly spelled
- ✅ Navigation works in both directions (back, forward)
- ✅ App survives force-quit and relaunch
- ✅ Network errors show user-friendly messages, not crashes
- ✅ Keyboard extension works in all text input fields
- ✅ Data persists across app termination
- ✅ No memory leaks (app doesn't slow over time)
- ✅ All 18 user journeys complete end-to-end

Any single failure reduces the score. Below 9.5 = **fail**, must fix and retest.

## What This Skill Does NOT Do

- ❌ No `xcodebuild`, `xcodegen`, or terminal commands
- ❌ No `curl` or direct API calls to backend
- ❌ No editing of source code, plist, or project files
- ❌ No LLDB/Xcode debugger
- ❌ No `bitrise build log` or `bitrise yml get`
- ❌ No SSH/ADB to device
- ❌ No simulator-only testing (real device required for final sign-off)
- ❌ No skipping steps because "the API should handle it"

## SuperCraftOS Human POV Test Execution

```bash
# All 18 tests are defined in .revyl/tests/
# Each test is pinned to Revyl build 834300f6-ff12-4a10-bf70-84eba1392252

# Run tests through Revyl (executes on real devices via Revyl device sessions)
/revyl test run fresh-ipa-installation-and-launch
/revyl test run onboarding-and-identity-configuration
/revyl test run memory-creation-and-retrieval
/revyl test run context-aware-ai-conversations
/revyl test run project-and-task-creation
/revyl test run agent-delegation
/revyl test run multi-agent-execution
/revyl test run workflow-creation-and-execution
/revyl test run document-ingestion-and-retrieval
/revyl test run artifact-generation
/revyl test run integration-connection-and-execution
/revyl test run model-switching-and-fallback
/revyl test run ai-keyboard-usage
/revyl test run data-persistence-after-app-termination
/revyl test run memory-modification-and-deletion
/revyl test run network-interruption-and-recovery
/revyl test run authentication-and-permissions
/revyl test run application-background-foreground-transitions
/revyl test run failure-handling-and-recovery
/revyl test run full-application-regression-testing

# Check results
/revyl test status <test-name>
/revyl test report <test-name>
```

## Defect Correction Cycle (Human POV)

1. **Reproduce** the issue through the UI only
2. **Document** with screenshots and exact steps
3. **Diagnose** root cause from user-visible behavior
4. **Fix** the source code (via Bitrise pipeline, not on-device)
5. **Rebuild** via Bitrise macOS Xcode stack
6. **Reinstall** the new IPA through Revyl
7. **Repeat** the failed test from step 1
8. **Run regression** on all 18 tests
9. **Record** verified result

## Sign-Off Criteria

Production-ready only when ALL of the following are true:

- [ ] All 18 human POV tests pass at 9.5/10 or higher
- [ ] Bitrise `primary` workflow builds successfully on macOS Xcode 27
- [ ] `.ipa` artifact produced and registered with Revyl
- [ ] Revyl E2E tests pass on real devices
- [ ] No critical bugs in any user journey
- [ ] App installs and launches on physical iOS device
- [ ] Keyboard extension works in all text fields
- [ ] Data persists across app termination
- [ ] Network errors handled gracefully
- [ ] Evidence collected for every test (screenshots, recordings, timestamps)
