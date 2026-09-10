export interface AgentSticker {
  id: string
  emoji: string
  bg: string
}

export interface AgentStickerCategory {
  title: string
  stickers: AgentSticker[]
}

const BG = [
  'bg-violet-600', 'bg-purple-600', 'bg-fuchsia-600', 'bg-pink-600',
  'bg-rose-600', 'bg-red-600', 'bg-orange-600', 'bg-amber-500',
  'bg-yellow-500', 'bg-lime-600', 'bg-green-600', 'bg-emerald-600',
  'bg-teal-600', 'bg-cyan-600', 'bg-sky-600', 'bg-blue-600',
  'bg-indigo-600', 'bg-violet-700', 'bg-slate-600', 'bg-zinc-600',
  'bg-stone-600', 'bg-red-700', 'bg-orange-700', 'bg-cyan-700',
] as const

function category(title: string, prefix: string, entries: readonly (readonly [string, string])[]): AgentStickerCategory {
  return {
    title,
    stickers: entries.map(([slug, emoji], i) => ({
      id: `${prefix}-${slug}`,
      emoji,
      bg: BG[i % BG.length],
    })),
  }
}

/** Netflix-style AI profile icons — emoji on vibrant square tiles, grouped by theme. */
export const AGENT_STICKER_CATEGORIES: AgentStickerCategory[] = [
  category('Robots & Machines', 'robot', [
    ['classic', '🤖'], ['arm', '🦾'], ['leg', '🦿'], ['alien', '👾'], ['ufo', '🛸'],
    ['satellite', '🛰️'], ['dish', '📡'], ['astronaut', '🧑‍🚀'], ['invader', '👽'], ['ghost', '👻'],
    ['joystick', '🕹️'], ['gamepad', '🎮'], ['desktop', '🖥️'], ['laptop', '💻'], ['keyboard', '⌨️'],
    ['mouse', '🖱️'], ['trackball', '🖲️'], ['printer', '🖨️'], ['fax', '📠'], ['pager', '📟'],
    ['radio', '📻'], ['tv', '📺'], ['camera-cctv', '📹'], ['video', '📽️'], ['projector', '📽️'],
    ['battery', '🔋'], ['plug', '🔌'], ['bulb', '💡'], ['flashlight', '🔦'], ['candle', '🕯️'],
    ['robot-face', '🤖'], ['mech', '🦾'], ['cyborg', '🦿'], ['space', '🛸'], ['comet', '☄️'],
  ]),
  category('AI Brain & Intelligence', 'brain', [
    ['mind', '🧠'], ['spark', '✨'], ['crystal', '🔮'], ['bolt', '⚡'], ['infinity', '♾️'],
    ['wand', '🪄'], ['cyclone', '🌀'], ['galaxy', '🌌'], ['planet', '🪐'], ['star', '🌟'],
    ['moon', '🌙'], ['sun', '☀️'], ['comet', '💫'], ['shooting', '🌠'], ['rainbow', '🌈'],
    ['dna', '🧬'], ['atom', '⚛️'], ['magnet', '🧲'], ['microscope', '🔬'], ['telescope', '🔭'],
    ['lab', '🧪'], ['alembic', '⚗️'], ['pill', '💊'], ['syringe', '💉'], ['stethoscope', '🩺'],
    ['xray', '🩻'], ['brain2', '🧠'], ['lightning', '🌩️'], ['fire', '🔥'], ['water', '💧'],
    ['snow', '❄️'], ['wind', '💨'], ['tornado', '🌪️'], ['volcano', '🌋'], ['earth', '🌍'],
    ['globe', '🌐'], ['map', '🗺️'], ['compass', '🧭'], ['anchor', '⚓'], ['gear', '⚙️'],
  ]),
  category('Agent Personas', 'persona', [
    ['coder-m', '👨‍💻'], ['coder-f', '👩‍💻'], ['coder', '🧑‍💻'], ['scientist', '🧑‍🔬'], ['teacher', '🧑‍🏫'],
    ['doctor', '🧑‍⚕️'], ['nurse', '👩‍⚕️'], ['business', '🧑‍💼'], ['detective', '🕵️'], ['hero', '🦸'],
    ['heroine', '🦸‍♀️'], ['wizard', '🧙'], ['witch', '🧙‍♀️'], ['genie', '🧞'], ['fairy', '🧚'],
    ['vampire', '🧛'], ['zombie', '🧟'], ['elf', '🧝'], ['juggler', '🤹'], ['clown', '🤡'],
    ['mask', '🎭'], ['prince', '🤴'], ['princess', '👸'], ['king', '🤴'], ['queen', '👸'],
    ['farmer', '🧑‍🌾'], ['cook', '🧑‍🍳'], ['artist', '🧑‍🎨'], ['pilot', '🧑‍✈️'], ['astronaut', '🧑‍🚀'],
    ['firefighter', '🧑‍🚒'], ['police', '👮'], ['guard', '💂'], ['construction', '👷'], ['mechanic', '🧑‍🔧'],
    ['factory', '🧑‍🏭'], ['judge', '🧑‍⚖️'], ['student', '🧑‍🎓'], ['singer', '🧑‍🎤'], ['dancer', '🧑‍💃'],
    ['runner', '🏃'], ['climber', '🧗'], ['swimmer', '🏊'], ['skier', '⛷️'], ['surfer', '🏄'],
    ['biker', '🚴'], ['lifter', '🏋️'], ['golfer', '🏌️'], ['fencer', '🤺'], ['wrestler', '🤼'],
    ['ninja', '🥷'], ['super', '🦸'], ['mage', '🧙'], ['santa', '🎅'], ['angel', '👼'],
  ]),
  category('Chat & Voice Agents', 'chat', [
    ['bubble', '💬'], ['speech', '🗨️'], ['thought', '💭'], ['shout', '🗯️'], ['speak', '🗣️'],
    ['headset', '🎧'], ['mic', '🎙️'], ['phone', '📞'], ['mobile', '📱'], ['pager', '📟'],
    ['email', '📧'], ['letter', '✉️'], ['inbox', '📥'], ['outbox', '📤'], ['megaphone', '📢'],
    ['bell', '🔔'], ['mute', '🔕'], ['loud', '🔊'], ['quiet', '🔇'], ['handshake', '🤝'],
    ['wave', '👋'], ['thumbs-up', '👍'], ['thumbs-down', '👎'], ['clap', '👏'], ['pray', '🙏'],
    ['point-up', '☝️'], ['point-right', '👉'], ['point-left', '👈'], ['ok', '👌'], ['peace', '✌️'],
    ['muscle', '💪'], ['brain-talk', '🧠'], ['robot-chat', '🤖'], ['search', '🔍'], ['target', '🎯'],
    ['globe', '🌐'], ['cloud', '☁️'], ['satellite', '📡'], ['signal', '📶'], ['wifi', '📶'],
    ['comment', '💬'], ['chatbot', '🤖'], ['help', '🆘'], ['info', 'ℹ️'], ['question', '❓'],
  ]),
  category('Code & Dev Agents', 'dev', [
    ['laptop', '💻'], ['desktop', '🖥️'], ['terminal', '⌨️'], ['mouse', '🖱️'], ['floppy', '💾'],
    ['cd', '💿'], ['dvd', '📀'], ['usb', '🔌'], ['bug', '🐛'], ['beetle', '🪲'],
    ['worm', '🪱'], ['ant', '🐜'], ['spider', '🕷️'], ['web', '🕸️'], ['scorpion', '🦂'],
    ['gear', '⚙️'], ['wrench', '🔧'], ['hammer', '🔨'], ['tools', '🛠️'], ['screwdriver', '🪛'],
    ['toolbox', '🧰'], ['nut', '🔩'], ['link', '🔗'], ['chain', '⛓️'], ['lock-code', '🔐'],
    ['key', '🔑'], ['shield-code', '🛡️'], ['file', '📄'], ['folder', '📁'], ['open-folder', '📂'],
    ['memo', '📝'], ['pencil', '✏️'], ['pen', '🖊️'], ['brush', '🖌️'], ['crayon', '🖍️'],
    ['bookmark', '🔖'], ['label', '🏷️'], ['clipboard', '📋'], ['card-index', '🗃️'], ['cabinet', '🗄️'],
    ['package', '📦'], ['inbox-tray', '📥'], ['outbox-tray', '📤'], ['scroll', '📜'], ['newspaper', '📰'],
    ['books', '📚'], ['book', '📖'], ['notebook', '📓'], ['ledger', '📒'], ['green-book', '📗'],
    ['blue-book', '📘'], ['orange-book', '📙'], ['dictionary', '📔'], ['grad', '🎓'], ['abc', '🔤'],
  ]),
  category('Data & Analytics', 'data', [
    ['chart-bar', '📊'], ['chart-up', '📈'], ['chart-down', '📉'], ['abacus', '🧮'], ['calculator', '🧮'],
    ['money-chart', '💹'], ['yen', '💴'], ['dollar', '💵'], ['euro', '💶'], ['pound', '💷'],
    ['money-bag', '💰'], ['coin', '🪙'], ['credit', '💳'], ['receipt', '🧾'], ['invoice', '🧾'],
    ['folder-org', '🗂️'], ['card-file', '🗃️'], ['cabinet', '🗄️'], ['clip', '📎'], ['link-paper', '🔗'],
    ['magnify', '🔎'], ['microscope', '🔬'], ['telescope', '🔭'], ['dna', '🧬'], ['petri', '🧫'],
    ['test-tube', '🧪'], ['thermometer', '🌡️'], ['bar-chart', '📊'], ['pie', '🥧'], ['graph', '📈'],
    ['table', '📋'], ['tabs', '📑'], ['page', '📄'], ['stats', '📊'], ['trend', '📈'],
    ['database', '🗄️'], ['server', '🖥️'], ['cloud-data', '☁️'], ['filter', '🔍'], ['sort', '🔀'],
    ['shuffle', '🔀'], ['repeat', '🔁'], ['loop', '🔂'], ['pin', '📌'], ['pushpin', '📍'],
    ['map-pin', '📍'], ['compass-data', '🧭'], ['globe-data', '🌍'], ['clock-data', '⏱️'], ['timer', '⏲️'],
  ]),
  category('Automation & Workflows', 'auto', [
    ['gear', '⚙️'], ['factory', '🏭'], ['robot-arm', '🦾'], ['conveyor', '🏭'], ['hammer', '🔨'],
    ['wrench', '🔧'], ['tools', '🛠️'], ['screwdriver', '🔩'], ['toolbox', '🧰'], ['link', '🔗'],
    ['plug', '🔌'], ['battery', '🔋'], ['rocket', '🚀'], ['airplane', '✈️'], ['helicopter', '🚁'],
    ['train', '🚂'], ['metro', '🚇'], ['tram', '🚊'], ['bus', '🚌'], ['truck', '🚚'],
    ['ship', '🚢'], ['anchor', '⚓'], ['ferry', '⛴️'], ['speedboat', '🚤'], ['bike', '🚲'],
    ['motorcycle', '🏍️'], ['car', '🚗'], ['taxi', '🚕'], ['police-car', '🚓'], ['ambulance', '🚑'],
    ['fire-truck', '🚒'], ['tractor', '🚜'], ['crane', '🏗️'], ['building', '🏢'], ['office', '🏢'],
    ['shuffle', '🔀'], ['repeat', '🔁'], ['loop', '🔂'], ['play', '▶️'], ['pause', '⏸️'],
    ['stop', '⏹️'], ['record', '⏺️'], ['next', '⏭️'], ['prev', '⏮️'], ['eject', '⏏️'],
    ['fast-fwd', '⏩'], ['rewind', '⏪'], ['up', '🔼'], ['down', '🔽'], ['refresh', '🔄'],
    ['arrows', '🔃'], ['clockwise', '🔃'], ['counter', '🔄'], ['hourglass', '⏳'], ['alarm', '⏰'],
  ]),
  category('Security & Guardrails', 'guard', [
    ['shield', '🛡️'], ['lock', '🔒'], ['unlock', '🔓'], ['key', '🔑'], ['old-key', '🗝️'],
    ['check', '✅'], ['cross', '❌'], ['warning', '⚠️'], ['stop-sign', '🛑'], ['sos', '🆘'],
    ['no-entry', '⛔'], ['prohibited', '🚫'], ['eye', '👁️'], ['eye-speech', '👁️‍🗨️'], ['nazar', '🧿'],
    ['police', '👮'], ['detective', '🕵️'], ['guard-face', '💂'], ['fire', '🚒'], ['ambulance', '🚑'],
    ['siren', '🚨'], ['badge', '🪪'], ['passport', '🛂'], ['customs', '🛃'], ['baggage', '🛄'],
    ['id', '🪪'], ['fingerprint', '🫆'], ['scan', '📠'], ['cctv', '📹'], ['camera', '📷'],
    ['binoculars', '🔭'], ['telescope-sec', '🔭'], ['flashlight-sec', '🔦'], ['dog', '🐕‍🦺'], ['eagle-eye', '🦅'],
    ['owl-watch', '🦉'], ['cat-watch', '🐈'], ['snake', '🐍'], ['dragon-guard', '🐉'], ['castle', '🏰'],
    ['fortress', '🏯'], ['door', '🚪'], ['window', '🪟'], ['fence', '🚧'], ['construction', '🚧'],
    ['helmet', '⛑️'], ['vest', '🦺'], ['gloves', '🧤'], ['mask-med', '😷'], ['biohazard', '☣️'],
  ]),
  category('Support & Service', 'support', [
    ['headset', '🎧'], ['phone', '☎️'], ['mobile', '📱'], ['envelope', '✉️'], ['package', '📦'],
    ['gift', '🎁'], ['ribbon', '🎀'], ['balloon', '🎈'], ['party', '🎉'], ['confetti', '🎊'],
    ['tada', '🎉'], ['heart', '❤️'], ['orange-heart', '🧡'], ['yellow-heart', '💛'], ['green-heart', '💚'],
    ['blue-heart', '💙'], ['purple-heart', '💜'], ['black-heart', '🖤'], ['white-heart', '🤍'], ['sparkle-heart', '💖'],
    ['growing-heart', '💗'], ['revolving', '💞'], ['two-hearts', '💕'], ['couple', '💑'], ['family', '👨‍👩‍👧'],
    ['people', '👥'], ['busts', '👥'], ['silhouette', '👤'], ['speaking', '🗣️'], ['raising-hand', '🙋'],
    ['bow', '🙇'], ['salute', '🫡'], ['hug', '🤗'], ['handshake', '🤝'], ['love-you', '🤟'],
    ['call-me', '🤙'], ['writing', '✍️'], ['nail-care', '💅'], ['selfie', '🤳'], ['smile', '😊'],
    ['grin', '😄'], ['cool', '😎'], ['thinking', '🤔'], ['nerd', '🤓'], ['monocle', '🧐'],
    ['relieved', '😌'], ['star-struck', '🤩'], ['halo', '😇'], ['wink', '😉'], ['sunglasses', '🕶️'],
  ]),
  category('Research & Science', 'science', [
    ['microscope', '🔬'], ['telescope', '🔭'], ['lab-coat', '🥼'], ['goggles', '🥽'], ['petri', '🧫'],
    ['test-tube', '🧪'], ['dna', '🧬'], ['syringe', '💉'], ['pill', '💊'], ['stethoscope', '🩺'],
    ['xray', '🩻'], ['drop-blood', '🩸'], ['bone', '🦴'], ['tooth', '🦷'], ['footprints', '👣'],
    ['brain-sci', '🧠'], ['atom', '⚛️'], ['magnet', '🧲'], ['battery-sci', '🔋'], ['bulb-sci', '💡'],
    ['fire-sci', '🔥'], ['water-sci', '💧'], ['snow-sci', '❄️'], ['comet-sci', '☄️'], ['volcano-sci', '🌋'],
    ['earth-sci', '🌍'], ['moon-sci', '🌙'], ['sun-sci', '☀️'], ['star-sci', '⭐'], ['galaxy-sci', '🌌'],
    ['plant', '🌱'], ['herb', '🌿'], ['four-leaf', '🍀'], ['tree', '🌳'], ['palm', '🌴'],
    ['cactus', '🌵'], ['flower', '🌸'], ['blossom', '🌼'], ['rose', '🌹'], ['tulip', '🌷'],
    ['sunflower', '🌻'], ['hibiscus', '🌺'], ['bouquet', '💐'], ['mushroom', '🍄'], ['leaf', '🍃'],
    ['fallen-leaf', '🍂'], ['maple', '🍁'], ['ear-rice', '🌾'], ['chestnut', '🌰'], ['seedling', '🌱'],
  ]),
  category('Creative & Design', 'creative', [
    ['palette', '🎨'], ['brush', '🖌️'], ['crayon', '🖍️'], ['pen', '🖊️'], ['pencil', '✏️'],
    ['memo', '📝'], ['spiral', '🗒️'], ['calendar', '📅'], ['tear-off', '📆'], ['card-index', '📇'],
    ['chart-creative', '📊'], ['pushpin', '📌'], ['round-pushpin', '📍'], ['paperclip', '📎'], ['link-creative', '🔗'],
    ['scissors', '✂️'], ['ruler', '📏'], ['tri-ruler', '📐'], ['abacus-c', '🧮'], ['file-c', '📁'],
    ['open-file', '📂'], ['card-box', '🗃️'], ['file-cabinet', '🗄️'], ['wastebasket', '🗑️'], ['lock-note', '🔐'],
    ['key-note', '🔑'], ['hammer-c', '🔨'], ['pick', '⛏️'], ['axe', '🪓'], ['saw', '🪚'],
    ['nut-bolt', '🔩'], ['gear-c', '⚙️'], ['chains', '⛓️'], ['hook', '🪝'], ['toolbox-c', '🧰'],
    ['magnet-c', '🧲'], ['ladder', '🪜'], ['plunger', '🪠'], ['screw', '🪛'], ['safety-pin', '🧷'],
    ['knot', '🪢'], ['thread', '🧵'], ['yarn', '🧶'], ['glasses', '👓'], ['dark-glasses', '🕶️'],
    ['goggles-c', '🥽'], ['lab-coat-c', '🥼'], ['safety-vest', '🦺'], ['necktie', '👔'], ['tshirt', '👕'],
    ['jeans', '👖'], ['dress', '👗'], ['kimono', '👘'], ['sari', '🥻'], ['bikini', '👙'],
    ['shorts', '🩳'], ['socks', '🧦'], ['gloves-c', '🧤'], ['scarf', '🧣'], ['coat', '🧥'],
  ]),
  category('Media & Content', 'media', [
    ['clapper', '🎬'], ['camera', '📷'], ['camera-flash', '📸'], ['video-cam', '📹'], ['film', '🎥'],
    ['tv', '📺'], ['radio', '📻'], ['studio-mic', '🎙️'], ['level-slider', '🎚️'], ['control-knobs', '🎛️'],
    ['music-note', '🎵'], ['notes', '🎶'], ['microphone', '🎤'], ['headphone', '🎧'], ['saxophone', '🎷'],
    ['guitar', '🎸'], ['keyboard-mus', '🎹'], ['trumpet', '🎺'], ['violin', '🎻'], ['banjo', '🪕'],
    ['drum', '🥁'], ['long-drum', '🪘'], ['maracas', '🪇'], ['flute', '🪈'], ['accordion', '🪗'],
    ['harp', '🪉'], ['dice', '🎲'], ['joker', '🃏'], ['mahjong', '🀄'], ['flower-card', '🎴'],
    ['performing', '🎭'], ['circus', '🎪'], ['ticket', '🎫'], ['admission', '🎟️'], ['art', '🎨'],
    ['framed', '🖼️'], ['museum', '🏛️'], ['classical', '🏛️'], ['scroll-media', '📜'], ['book-media', '📚'],
    ['newspaper-m', '📰'], ['rolled', '🗞️'], ['bookmark-m', '🔖'], ['label-m', '🏷️'], ['money-m', '💰'],
    ['gem', '💎'], ['ring', '💍'], ['crown', '👑'], ['trophy-m', '🏆'], ['medal', '🏅'],
    ['military', '🎖️'], ['sports-medal', '🏅'], ['first', '🥇'], ['second', '🥈'], ['third', '🥉'],
    ['soccer', '⚽'], ['basketball', '🏀'], ['football', '🏈'], ['baseball', '⚾'], ['tennis', '🎾'],
    ['volleyball', '🏐'], ['rugby', '🏉'], ['8ball', '🎱'], ['ping-pong', '🏓'], ['badminton', '🏸'],
  ]),
  category('Commerce & Operations', 'ops', [
    ['cart', '🛒'], ['store', '🏪'], ['convenience', '🏪'], ['department', '🏬'], ['mall', '🛍️'],
    ['shopping-bags', '🛍️'], ['gift-ops', '🎁'], ['wrapped', '🎁'], ['ribbon-ops', '🎀'], ['package-ops', '📦'],
    ['postbox', '📮'], ['mailbox', '📫'], ['closed-mail', '📪'], ['open-mail', '📬'], ['mail-sent', '📭'],
    ['incoming', '📨'], ['envelope-arrow', '📩'], ['flying-env', '💌'], ['receipt-ops', '🧾'], ['chart-ops', '💹'],
    ['yen-ops', '💴'], ['dollar-ops', '💵'], ['euro-ops', '💶'], ['pound-ops', '💷'], ['money-wings', '💸'],
    ['credit-ops', '💳'], ['coin-ops', '🪙'], ['money-bag-ops', '💰'], ['gem-ops', '💎'], ['balance', '⚖️'],
    ['calendar-ops', '📅'], ['spiral-cal', '🗓️'], ['clock-ops', '🕐'], ['watch', '⌚'], ['timer-ops', '⏱️'],
    ['stopwatch', '⏱️'], ['alarm-ops', '⏰'], ['hourglass-ops', '⏳'], ['hourglass-done', '⌛'], ['bell-ops', '🔔'],
    ['map-ops', '🗺️'], ['world-map', '🗺️'], ['compass-ops', '🧭'], ['place', '📍'], ['round-pin', '📌'],
    ['airplane-ops', '✈️'], ['departure', '🛫'], ['arrival', '🛬'], ['helicopter-ops', '🚁'], ['ship-ops', '🚢'],
    ['anchor-ops', '⚓'], ['fuel', '⛽'], ['construction-ops', '🚧'], ['barrier', '🚧'], ['traffic', '🚦'],
    ['vertical-traffic', '🚦'], ['stop-light', '🚥'], ['warning-ops', '⚠️'], ['children-cross', '🚸'], ['no-entry-ops', '⛔'],
  ]),
  category('Animal Agents', 'animal', [
    ['owl', '🦉'], ['parrot', '🦜'], ['eagle', '🦅'], ['duck', '🦆'], ['swan', '🦢'],
    ['peacock', '🦚'], ['flamingo', '🦩'], ['dove', '🕊️'], ['penguin', '🐧'], ['chicken', '🐔'],
    ['rooster', '🐓'], ['hatching', '🐣'], ['bird', '🐦'], ['baby-chick', '🐤'], ['turkey', '🦃'],
    ['dog', '🐕'], ['service-dog', '🐕‍🦺'], ['guide-dog', '🦮'], ['poodle', '🐩'], ['wolf', '🐺'],
    ['fox', '🦊'], ['raccoon', '🦝'], ['cat', '🐈'], ['black-cat', '🐈‍⬛'], ['lion', '🦁'],
    ['tiger', '🐯'], ['leopard', '🐆'], ['horse', '🐴'], ['unicorn', '🦄'], ['zebra', '🦓'],
    ['deer', '🦌'], ['bison', '🦬'], ['cow', '🐮'], ['ox', '🐂'], ['water-buffalo', '🐃'],
    ['pig', '🐷'], ['boar', '🐗'], ['ram', '🐏'], ['sheep', '🐑'], ['goat', '🐐'],
    ['camel', '🐫'], ['two-hump', '🐫'], ['llama', '🦙'], ['giraffe', '🦒'], ['elephant', '🐘'],
    ['mammoth', '🦣'], ['rhino', '🦏'], ['hippo', '🦛'], ['mouse', '🐭'], ['rat', '🐀'],
    ['hamster', '🐹'], ['rabbit', '🐇'], ['chipmunk', '🐿️'], ['beaver', '🦫'], ['hedgehog', '🦔'],
    ['bat', '🦇'], ['bear', '🐻'], ['polar-bear', '🐻‍❄️'], ['koala', '🐨'], ['panda', '🐼'],
    ['sloth', '🦥'], ['otter', '🦦'], ['skunk', '🦨'], ['kangaroo', '🦘'], ['badger', '🦡'],
    ['feet', '🐾'], ['turkey-bird', '🦃'], ['dodo', '🦤'], ['monkey', '🐒'], ['gorilla', '🦍'],
    ['orangutan', '🦧'], ['chimp', '🐵'], ['frog', '🐸'], ['crocodile', '🐊'], ['turtle', '🐢'],
    ['lizard', '🦎'], ['snake-animal', '🐍'], ['dragon-face', '🐲'], ['dragon', '🐉'], ['sauropod', '🦕'],
    ['t-rex', '🦖'], ['whale', '🐳'], ['dolphin-animal', '🐬'], ['seal', '🦭'], ['fish', '🐟'],
    ['tropical-fish', '🐠'], ['blowfish', '🐡'], ['shark', '🦈'], ['octopus', '🐙'], ['shell', '🐚'],
    ['coral', '🪸'], ['jellyfish', '🪼'], ['crab', '🦀'], ['lobster', '🦞'], ['shrimp', '🦐'],
    ['squid', '🦑'], ['snail', '🐌'], ['butterfly', '🦋'], ['bug-animal', '🐛'], ['ant-animal', '🐜'],
    ['bee', '🐝'], ['beetle-animal', '🪲'], ['cockroach', '🪳'], ['fly', '🪰'], ['worm-animal', '🪱'],
    ['microbe', '🦠'], ['bouquet-animal', '💐'], ['cherry-blossom', '🌸'], ['white-flower', '💮'], ['rosette', '🏵️'],
  ]),
  category('Food & Fun Agents', 'fun', [
    ['pizza', '🍕'], ['burger', '🍔'], ['fries', '🍟'], ['hotdog', '🌭'], ['sandwich', '🥪'],
    ['taco', '🌮'], ['burrito', '🌯'], ['tamale', '🫔'], ['stuffed-flatbread', '🥙'], ['falafel', '🧆'],
    ['egg', '🥚'], ['cooking', '🍳'], ['shallow-pan', '🥘'], ['pot', '🍲'], ['fondue', '🫕'],
    ['bowl', '🥣'], ['salad', '🥗'], ['popcorn', '🍿'], ['butter', '🧈'], ['salt', '🧂'],
    ['canned', '🥫'], ['bento', '🍱'], ['rice', '🍚'], ['curry', '🍛'], ['ramen', '🍜'],
    ['spaghetti', '🍝'], ['sweet-potato', '🍠'], ['oden', '🍢'], ['sushi', '🍣'], ['fried-shrimp', '🍤'],
    ['fish-cake', '🍥'], ['moon-cake', '🥮'], ['dango', '🍡'], ['dumpling', '🥟'], ['fortune-cookie', '🥠'],
    ['takeout', '🥡'], ['crab-fun', '🦀'], ['lobster-fun', '🦞'], ['shaved-ice', '🍧'], ['ice-cream', '🍨'],
    ['doughnut', '🍩'], ['cookie', '🍪'], ['birthday', '🎂'], ['cake', '🍰'], ['cupcake', '🧁'],
    ['pie-fun', '🥧'], ['chocolate', '🍫'], ['candy', '🍬'], ['lollipop', '🍭'], ['custard', '🍮'],
    ['honey', '🍯'], ['baby-bottle', '🍼'], ['milk', '🥛'], ['coffee', '☕'], ['teapot', '🫖'],
    ['tea', '🍵'], ['sake', '🍶'], ['champagne', '🍾'], ['wine', '🍷'], ['cocktail', '🍸'],
    ['tropical-drink', '🍹'], ['beer', '🍺'], ['clinking-beer', '🍻'], ['bottle', '🍾'], ['cup-straw', '🥤'],
    ['bubble-tea', '🧋'], ['beverage', '🥤'], ['mate', '🧉'], ['ice', '🧊'], ['spoon', '🥄'],
    ['fork-knife', '🍴'], ['plate', '🍽️'], ['chopsticks', '🥢'], ['jar', '🫙'], ['amphora', '🏺'],
  ]),
  category('Symbols & Power-Ups', 'symbol', [
    ['check-mark', '✅'], ['x-mark', '❌'], ['question-red', '❓'], ['question-white', '❔'], ['exclamation-red', '❗'],
    ['exclamation-white', '❕'], ['hundred', '💯'], ['anger', '💢'], ['sweat', '💦'], ['dash-symbol', '💨'],
    ['hole', '🕳️'], ['bomb', '💣'], ['speech-anger', '🗯️'], ['zzz', '💤'], ['sparkle', '✨'],
    ['star-symbol', '⭐'], ['glowing-star', '🌟'], ['dizzy', '💫'], ['boom', '💥'], ['collision', '💥'],
    ['sweat-drops', '💦'], ['droplet', '💧'], ['high-voltage', '⚡'], ['fire-symbol', '🔥'], ['snowflake', '❄️'],
    ['snowman', '⛄'], ['snowman-snow', '☃️'], ['comet-symbol', '☄️'], ['rainbow-symbol', '🌈'], ['umbrella', '☂️'],
    ['umbrella-rain', '☔'], ['cloud-symbol', '☁️'], ['cloud-rain', '🌧️'], ['cloud-lightning', '⛈️'], ['tornado-symbol', '🌪️'],
    ['fog', '🌫️'], ['wind-face', '🌬️'], ['cyclone-symbol', '🌀'], ['globe-symbol', '🌐'], ['map-symbol', '🗺️'],
    ['mountain', '⛰️'], ['volcano-symbol', '🌋'], ['camping', '🏕️'], ['beach', '🏖️'], ['desert', '🏜️'],
    ['island', '🏝️'], ['park', '🏞️'], ['stadium', '🏟️'], ['classical-building', '🏛️'], ['building-construction', '🏗️'],
    ['houses', '🏘️'], ['derelict', '🏚️'], ['house', '🏠'], ['home', '🏡'], ['house-garden', '🏡'],
    ['office-symbol', '🏢'], ['post-office', '🏣'], ['european-post', '🏤'], ['hospital', '🏥'], ['bank', '🏦'],
    ['hotel', '🏨'], ['love-hotel', '🏩'], ['convenience-symbol', '🏪'], ['school', '🏫'], ['department-symbol', '🏬'],
    ['factory-symbol', '🏭'], ['japanese-castle', '🏯'], ['castle-symbol', '🏰'], ['wedding', '💒'], ['tokyo-tower', '🗼'],
    ['statue', '🗽'], ['church', '⛪'], ['mosque', '🕌'], ['hindu-temple', '🛕'], ['synagogue', '🕍'],
    ['shinto', '⛩️'], ['kaaba', '🕋'], ['fountain', '⛲'], ['tent', '⛺'], ['foggy', '🌁'],
    ['night-stars', '🌃'], ['cityscape', '🏙️'], ['sunrise', '🌅'], ['sunrise-mountains', '🌄'], ['city-dusk', '🌆'],
    ['city-sunset', '🌇'], ['bridge', '🌉'], ['carousel', '🎠'], ['ferris', '🎡'], ['roller-coaster', '🎢'],
    ['barber', '💈'], ['circus-tent', '🎪'], ['locomotive', '🚂'], ['railway', '🚃'], ['bullet-train', '🚄'],
    ['train-symbol', '🚆'], ['metro-symbol', '🚇'], ['light-rail', '🚈'], ['station', '🚉'], ['tram-symbol', '🚊'],
    ['monorail', '🚝'], ['mountain-rail', '🚞'], ['tram-car', '🚋'], ['bus-symbol', '🚌'], ['trolleybus', '🚎'],
    ['minibus', '🚐'], ['ambulance-symbol', '🚑'], ['fire-engine', '🚒'], ['police-symbol', '🚓'], ['oncoming-police', '🚔'],
    ['taxi-symbol', '🚕'], ['oncoming-taxi', '🚖'], ['car-symbol', '🚗'], ['oncoming-car', '🚘'], ['suv', '🚙'],
    ['pickup', '🛻'], ['delivery', '🚚'], ['articulated', '🚛'], ['tractor-symbol', '🚜'], ['racing-car', '🏎️'],
    ['motorcycle-symbol', '🏍️'], ['scooter', '🛵'], ['manual-wheelchair', '🦽'], ['motor-wheelchair', '🦼'], ['auto-rickshaw', '🛺'],
    ['bike-symbol', '🚲'], ['kick-scooter', '🛴'], ['skateboard', '🛹'], ['roller-skate', '🛼'], ['bus-stop', '🚏'],
    ['motorway', '🛣️'], ['railway-track', '🛤️'], ['oil', '🛢️'], ['fuel-pump', '⛽'], ['wheel', '🛞'],
    ['rotating-light', '🚨'], ['horizontal-traffic', '🚥'], ['vertical-traffic-symbol', '🚦'], ['octagonal-sign', '🛑'], ['construction-symbol', '🚧'],
  ]),
]

export const ALL_AGENT_STICKERS = AGENT_STICKER_CATEGORIES.flatMap(c => c.stickers)

export const DEFAULT_AGENT_STICKER_ID = ALL_AGENT_STICKERS[0].id

const stickerById = new Map(ALL_AGENT_STICKERS.map(s => [s.id, s]))

export function getAgentSticker(id: string | null | undefined): AgentSticker | undefined {
  if (!id) return undefined
  return stickerById.get(id)
}

export function isAgentStickerId(value: string | null | undefined): boolean {
  return !!value && stickerById.has(value)
}

export const STICKER_COUNT = ALL_AGENT_STICKERS.length
