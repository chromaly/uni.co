# Firebase access for assistant memory

The backend uses the signed-in user's Firebase ID token, not an Admin SDK database
client. Existing Firestore Security Rules still apply to every operation.

If your rules already permit a user to access their own subcollections, no extra
rule may be needed. Otherwise merge the following match block **inside your existing
`match /databases/{database}/documents` block**. Do not replace your Planner rules
with this snippet, and do not turn off App Check or broaden access to other users.

```text
match /users/{userId}/assistantMemories/{memoryId} {
  function ownsMemory() {
    return request.auth != null && request.auth.uid == userId;
  }

  allow read, delete: if ownsMemory();

  allow create, update: if ownsMemory()
    && request.resource.data.keys().hasAll([
      'content', 'type', 'sourceText', 'createdAt', 'updatedAt'
    ])
    && request.resource.data.keys().hasOnly([
      'content', 'type', 'sourceText', 'createdAt', 'updatedAt'
    ])
    && request.resource.data.content is string
    && request.resource.data.content.size() > 0
    && request.resource.data.content.size() <= 2000
    && request.resource.data.type in ['preference', 'fact', 'goal', 'project']
    && request.resource.data.sourceText is string
    && request.resource.data.sourceText.size() <= 4000
    && request.resource.data.createdAt is timestamp
    && request.resource.data.updatedAt is timestamp;
}
```

A 403 from `/memory` or `/memory/search` means access was rejected; check the rules
and any configured App Check enforcement. Do not interpret an error as empty memory.

This is a rule example for the new collection, not a full audit of your deployed
rules. Overlapping broad allow rules cannot be restricted by adding a narrower one.
