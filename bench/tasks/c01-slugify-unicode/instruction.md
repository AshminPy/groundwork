`textkit.slug.slugify` produces bad slugs for titles with accents and punctuation. For example
`slugify("Crème Brûlée -- Recipe!")` should return `creme-brulee-recipe`. Fix it: letters with accents become plain
ASCII letters, anything that is not a letter or digit becomes a single dash, there are no leading, trailing or
repeated dashes, and the result is lowercase. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
