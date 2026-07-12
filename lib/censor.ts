const BAD_WORDS = [
  "fuck",
  "shit",
  "bitch",
  "asshole",
  "dick",
  "pussy",
  "cunt",
  "motherfucker",
  "bastard",
  "nigger",
  "faggot",
]

export function censorWord(word: string): string {
  if (!word) return word

  // Clean the word for comparison (remove punctuation, lower case)
  const cleanWord = word.toLowerCase().replace(/[.,!?;:]/g, "")

  const needsCensoring = BAD_WORDS.some((bad) => {
    // Exact match or starts with bad word (e.g. fucking, shitting)
    return (
      cleanWord === bad || (cleanWord.length > 3 && cleanWord.startsWith(bad))
    )
  })

  if (needsCensoring) {
    // Replace the second character with an asterisk
    // Handle punctuation preservation
    const punctuation = word.match(/[.,!?;:]+$/)
    const baseWord = punctuation ? word.slice(0, -punctuation[0].length) : word

    if (baseWord.length <= 1) return word

    const censored = baseWord[0] + "*" + baseWord.slice(2)
    return censored + (punctuation ? punctuation[0] : "")
  }

  return word
}
