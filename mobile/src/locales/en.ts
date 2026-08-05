export const en = {
  common: {
    back: 'Back', cancel: 'Cancel', close: 'Close', continue: 'Continue', retry: 'Retry',
    save: 'Save', skip: 'Skip', loading: 'Loading…', error: 'Something went wrong.',
  },
  auth: {
    title: 'Welcome to Kawu', subtitle: 'Sign in to capture your showing.', email: 'Email',
    password: 'Password', login: 'Sign in', invalid: 'Check your email and password.',
  },
  home: {
    title: 'Kawu Capture', start: 'Start Showing', recent: 'Recent showings',
    empty: 'No showings yet. Start one when you arrive.', signOut: 'Sign out',
    syncNow: 'Sync now', report: 'View report', untitled: 'Untitled showing',
  },
  setup: {
    title: 'New showing', client: 'Client (optional)', property: 'Property (optional)',
    address: 'Or type a new address', search: 'Search', noClient: 'No client',
    noProperty: 'Add later', begin: 'Begin recording', addressPlaceholder: '123 Main Street',
  },
  recording: {
    title: 'Showing in progress', recording: 'Recording', interrupted: 'Recording interrupted',
    resume: 'Resume recording', photo: 'Photo', voiceTag: 'Voice Tag', end: 'End',
    endTitle: 'End this showing?', endBody: 'Kawu will sync all captured media, then begin processing.',
    endConfirm: 'End and sync', permission: 'Microphone access is required to record a showing.',
    cameraPermission: 'Camera access is required to attach photos.', tagged: 'Voice tag saved',
    photoSaved: 'Photo saved', recovering: 'Recovered recording. Tap resume to continue.',
  },
  sync: {
    local: 'Local', syncing: 'Syncing', synced: 'Synced', processing: 'Processing', ready: 'Ready',
    failed: 'Needs retry', offline: 'Offline — saved safely on this device',
  },
  report: {
    title: 'Draft report', summary: 'Executive summary', rooms: 'Room by room',
    highlights: 'Highlights', concerns: 'Concerns', followUps: 'Follow-ups',
    observations: 'Observations', edit: 'Fix typo', deleteObservation: 'Delete observation',
    confirm: 'Confirm report', send: 'Create share link', desktop: 'Review on desktop',
    desktopBody: 'Sensitive or unreviewed items need the full dashboard before this report can be confirmed.',
    propertyRequired: 'Attach a property on the desktop dashboard before confirming this report.',
    noReport: 'The draft report is still processing.', sensitive: 'Sensitive item requires review',
    saved: 'Report updated', dismissed: 'Observation removed', shared: 'Share link created',
  },
} as const;
