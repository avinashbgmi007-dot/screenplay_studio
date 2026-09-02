// _payload.js — shared demo content for all six preview-next worlds (design artifact;
// not wired to any backend). Same data everywhere so the comparison isolates design.
window.PAYLOAD = {
  project: { title: "The Second Shift", author: "A. Writer", format: "fountain",
             scenes: 4, pages: 9.5, analyzed: true },

  script: [
    { n: 1, slug: "INT. CITY HOSPITAL - WARD 3 - NIGHT", int_ext: "INT", time: "NIGHT", page: "1-2.5",
      elements: [
        ["action", "Rain hammers the windows. MEERA (32), badge LATCHA-NURSE, works the row of beds with a torch she doesn't need — she knows this ward blind."],
        ["dialogue", "AMMA", "Tiffin pettanu. Tinu, ayite night duty lo tiyyalsina avasaram ledu."],
        ["parenthetical", "(in Telugu; subtitled)"],
        ["dialogue", "MEERA", "Amma, two minutes. Sister will catch me."],
        ["action", "She takes the box anyway. It is warm. That undoes her a little."],
        ["dialogue", "MEERA (CONT'D)", "I'll eat. Promise. Nenu vasthanu."],
        ["action", "At the last bed, RAO GARU lies exactly as he has for 61 days. She checks his chart, writes nothing, moves on."],
        ["transition", "CUT TO:"]] },
    { n: 2, slug: "INT. CITY HOSPITAL - NURSES STATION - CONTINUOUS", int_ext: "INT", time: "NIGHT", page: "2.5-5",
      elements: [
        ["action", "The station at 2 AM: three cold coffees, one ringing phone nobody answers. MEERA files charts. VIKRAM (38), rain-soaked, stands on the wrong side of the counter holding an envelope like evidence."],
        ["dialogue", "VIKRAM", "Complaint file chesanu. Managing trustee ki direct ga. Copy ikkada."],
        ["action", "He slides the envelope across. She doesn't touch it."],
        ["dialogue", "MEERA", "Hospital rules are rules, Vikram. Visiting hours end at nine."],
        ["dialogue", "VIKRAM", "Rules. Adhi nuvvu chepputunnava? Idigo raatri pandupu —"],
        ["action", "He empties the envelope: photographs of the ward, taken through the gate, nights. She scans them too fast to have read them."],
        ["dialogue", "VIKRAM (CONT'D)", "Evaru choosina ninnu choosaru. Nenu matrame kadhu."],
        ["action", "The phone stops ringing. Nobody has answered it. This is the longest silence in the script."],
        ["transition", "MATCH CUT TO:"]] },
    { n: 3, slug: "INT. CITY HOSPITAL - WARD 3 - LATER THAT NIGHT", int_ext: "INT", time: "NIGHT", page: "5-7.5",
      elements: [
        ["action", "Meera's torch beam finds Rao Garu's window — the glass dark, the ward beyond it darker. She unlocks his bed rail."],
        ["dialogue", "MEERA", "(under her breath) Kasi kasi mandhu okate rhythm lo padutundi... kaani Ee song ki."],
        ["action", "She sings — low, half-spoken, a lullaby their mother sang. And Rao Garu's finger curls. Once. Deliberate."],
        ["action", "In the doorway, unlit: VIKRAM. He has seen it. He does not move."],
        ["dialogue", "VIKRAM", "Idhi... complaints book lo ledu."],
        ["action", "Meera stands very still. The song is over. Neither of them closes the door."]] },
    { n: 4, slug: "EXT. CITY HOSPITAL - AMBULANCE BAY - DAWN", int_ext: "EXT", time: "DAWN", page: "7.5-9.5",
      elements: [
        ["action", "The city lights thin out. VIKRAM waits by the ambulance bay. MEERA comes out, badge turned backwards."],
        ["dialogue", "VIKRAM", "Ninnu suspend chestaru."],
        ["dialogue", "MEERA", "Suspend aithe patient lepotadu."],
        ["dialogue", "AMMA", "(from the shadows, holding the empty tiffin) Iddaru intiki. Ippudu."],
        ["action", "Amma walks. They follow. Nobody has won. The complaint envelope stays in Vikram's pocket, dry now."]] }],

  findings: [
    { id: 1, severity: "high", category: "structure", scene: 3,
      note: "The discovery — the script's only true surprise — arrives at scene 3 of 4. Everything before it is setup; everything after is one scene. The midpoint owns the story and the back half doesn't push back.",
      quote: "And Rao Garu's finger curls. Once. Deliberate.", verified: true },
    { id: 2, severity: "high", category: "dialogue", scene: 2,
      note: "Vikram shifts register mid-scene: legal-brief Tenglish in one line, wounded intimacy two lines later. It reads as two characters, not one man cracking.",
      quote: "Rules. Adhi nuvvu chepputunnava? Idigo raatri pandupu —", verified: true },
    { id: 3, severity: "high", category: "scene_function", scene: 2,
      note: "Scene 2 has motion but no want and no obstacle — Meera receives information and changes nothing. The scene stalls; the phone that nobody answers is the scene telling you so.",
      quote: "The phone stops ringing. Nobody has answered it.", verified: true },
    { id: 4, severity: "medium", category: "plot_thread", scene: 1,
      note: "The warm tiffin is planted as Meera's one soft spot — then vanishes. If it returns at dawn it's the emotional spine; right now it's a prop.",
      quote: "She takes the box anyway. It is warm.", verified: true },
    { id: 5, severity: "medium", category: "character", scene: 4,
      note: "Amma settles the standoff in one line from off-frame. A decisive mother is a great engine — but she needs one earlier beat so the turn isn't borrowed from nowhere.",
      quote: "(from the shadows, holding the empty tiffin) Iddaru intiki. Ippudu.", verified: true },
    { id: 6, severity: "medium", category: "subtext", scene: 2,
      note: "On the nose: Meera states the theme instead of defending it. Let her justify with a detail (a patient's name, a shift count) and the line does the arguing itself.",
      quote: "Hospital rules are rules, Vikram. Visiting hours end at nine.", verified: true },
    { id: 7, severity: "medium", category: "continuity", scene: 4,
      note: "Time-of-day flips NIGHT to DAWN with no LATER/SUPER marker. The checker flags it; the reader feels it without knowing why.",
      quote: "EXT. CITY HOSPITAL - AMBULANCE BAY - DAWN", verified: true },
    { id: 8, severity: "low", category: "plot_thread", scene: 3,
      note: "Rao Garu's finger moves once — an un-earned miracle if nothing smaller precedes it. (Could not match this quote against the script text; flagged unverified.)",
      quote: "His hand twitched at the wrist, the monitor blipping.", verified: false },
    { id: 9, severity: "low", category: "structure", scene: 4,
      note: "No darkest hour: the suspension threat is spoken and immediately soothed by Amma. One beat of true cost before the walk home would land the ending.",
      quote: "Ninnu suspend chestaru.", verified: true } ],

  coverage: {
    logline: "When a night-shift nurse discovers her comatose patient wakes only when she sings, she must choose between the hospital's rules and the one thing that still works.",
    genre: "Family drama / medical",
    synopsis: "Meera has kept Ward 3 alive on routine for 61 days. Her brother Vikram files a complaint against the hospital with her at its center. On the night the complaint lands, Meera's private ritual — singing to a comatose man who no one expects to wake — is witnessed. Dawn forces the family to decide what the complaint was actually for.",
    recommendation: "PASS with reservations — a compact, shootable four-scene chamber piece; expand the middle and let the mother in earlier." },

  pacing: [
    { scene: 1, density: 0.62, action_share: 41, pace: 0.71, drag: false },
    { scene: 2, density: 0.38, action_share: 62, pace: 0.31, drag: true  },
    { scene: 3, density: 0.81, action_share: 47, pace: 0.88, drag: false },
    { scene: 4, density: 0.66, action_share: 38, pace: 0.74, drag: false } ],

  dials: [
    { character: "MEERA",    scenes: [1,2,3,4], poles: { proactive: 6, warm: 8, articulate: 7, emotional: 5, grounded: 8 } },
    { character: "VIKRAM",   scenes: [2,3,4],   poles: { proactive: 9, warm: 3, articulate: 8, emotional: 7, grounded: 4 } },
    { character: "AMMA",     scenes: [1,4],     poles: { proactive: 7, warm: 9, articulate: 5, emotional: 6, grounded: 9 } },
    { character: "RAO GARU", scenes: [1,3],     poles: { proactive: 2, warm: 5, articulate: 1, emotional: 4, grounded: 3 } } ],

  ledger: [
    { setup: "The warm tiffin box",   kind: "object",   setup_scene: 1, status: "dangling",  note: "Planted as Meera's soft spot; never returns until Amma holds it empty — the payoff is implied, never staged." },
    { setup: "The complaint envelope", kind: "object",  setup_scene: 2, status: "abandoned", note: "Drives scenes 2-3, then stays dry in Vikram's pocket. Either the stakes or the envelope needs an ending." },
    { setup: "The singing ritual",    kind: "ritual",   setup_scene: 3, status: "paid",      note: "Witnessed, confronted, and chosen at dawn — the script's one fully paid promise." },
    { setup: "Nobody answers the phone", kind: "motif", setup_scene: 2, status: "dangling",  note: "Rings twice, never answered, never explained. One line makes it the ward's whole condition." } ],

  reads: [
    { character: "MEERA",  read: "Comes across as dutiful to the point of eraseable — the script wants her cornered, but she complies so smoothly we never see what defiance costs her." },
    { character: "VIKRAM", read: "Played as the antagonist; written, probably, as the only family member doing something. The complaint should read as love with bad handwriting — it currently reads as process serving." } ]
};
