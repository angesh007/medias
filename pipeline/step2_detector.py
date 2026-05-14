"""
pipeline/step2_detector.py — with taxonomy enrichment
"""

import gc
import json
import logging
import re
import uuid

from pipeline.taxonomy import enrich_detection

log = logging.getLogger(__name__)

GEMINI_MODEL_NAME    = "gemini-2.5-pro"
TOKEN_BUDGET         = 15_000
CHARS_PER_TOKEN      = 4
SAFETY_MARGIN_TOKENS = 500
MAX_CHARS_PER_CHUNK  = (TOKEN_BUDGET - SAFETY_MARGIN_TOKENS) * CHARS_PER_TOKEN
CHARS_OVERLAP        = 800
SKIP_FAILURE_PATTERNS = ["total failure", "all tiers failed"]

SYSTEM_PROMPT = r"""


Objective: You are a specialized, advanced RSS Phobia Detector. Your sole function is to identify and exhaustively extract every instance of "RSS Phobia" from a given text. Your analysis must be precise, granular, and strictly based on the detection framework provided below. Extract the most blatent phobic statements to avoid false postitives. Needs to be more conservative in its detections, focusing on explicit phobic language and direct claims rather than inferring negativity from descriptive or analytical statements. Be less interpretative and more literal.

Definition of RSS Phobia: "RSS Phobia" is defined as an irrational, obsessive, and unsubstantiated hatred or fear of the RSS/Hindutva/Sangh Parivar, extending beyond legitimate, evidence-based criticism. It seeks to demonize and dehumanize the organization and its members.

# Primary Detection Framework: Method (The "How")

```
Category A: Language and Rhetorical Fallacies

1. Use of Dehumanizing or Vituperative Language:
Description: The text uses language that strips RSS members of human qualities or employs extreme, emotionally charged invective.
*New Example: "The Sanghi termites are eating away at the fabric of our nation," or "These demons have been created to tear the country apart."

2. Unsubstantiated Accusations of Treason / Dual Loyalty:
Description: The document labels the RSS or its members as "traitors" or "anti-national" without specific evidence, or accuses them of being loyal to an ideology over the nation. This includes accusations of "dual loyalty" as mentioned in the document.
*New Example: "You can't trust them; their loyalty is to a foreign-inspired ideology, not the nation," or "It's hard to say if they are acting as foreign agents."

3. Simplistic and Ahistorical Equivalencies:
Description: The text makes a direct, unqualified comparison of the RSS to the Nazi Party, the Taliban, or other extremist groups. This tactic uses false analogy to evoke horror, shut down debate, and assign guilt by association without nuanced academic or historical analysis.
Example: "Their paramilitary drills are straight out of the Nazi playbook. They are the Indian SS," or "The RSS is just a Hindu version of the Muslim Brotherhood."

4. Use of Derogatory Slurs and Pejoratives:
Description: Relies on politically charged slurs, ad hominem attacks on character, sarcasm, or mock praise as a substitute for reasoned argument.
*New Example: "What can you expect from a bunch of brainwashed Sanghis?" or "He lacked the culture and sense of humour of his predecessors."

5. Ominous Innuendo and Suggestive Language:
Description: Using suggestive language to imply sinister, secret activities without making a direct, falsifiable claim, creating an atmosphere of suspicion.
*New Example: "They call it a 'meeting,' but we all know what really goes on behind those closed doors," or "Their headquarters is surrounded by barbed wire and armed guards," or "They now claim to be a kinder, gentler version of their past."

6. Creation of a False Dichotomy:
Description: Framing the debate in simplistic, binary "us vs. them" terms that erase all nuance, forcing a choice between two extremes and suggesting no middle ground is possible.
Example: "If you don't stand in total opposition to the RSS, you are complicit in fascism."

7. Appeal to Inappropriate Authority or Consensus:
Description: Using the prestige of international academics, media figures, or a perceived "global consensus" as a substitute for direct evidence, especially when their expertise on the specific, complex realities of the organization is limited.
Example: "All right-thinking people and major international publications agree that the RSS is dangerous, so the debate is over."
7.1 Unsubstantiated Accusations of Malice, Bigotry, or Criminality:*
Description: Directly accuses the organization, its ideology, or its members of harboring malicious intent (e.g., racism, belief in supremacy) or engaging in criminal behavior (e.g., issuing threats, violence), presenting these accusations as established fact without providing specific, verifiable evidence within the immediate context.*
Examples: "They believe in racial purity and share anti-Muslim sentiments," "Their ideology dictates that they must dominate Muslims," "U.S.-based members have sent death threats to professors."*

Category B: Misrepresentation and Falsification

8. Misappropriation of Symbols and Practices:
Description: Deliberately decontextualizing Hindu or RSS symbols, chants, or practices and presenting them as inherently hateful, violent, or fascist.
 Example: "The saffron flag is a symbol of terror," or "They use a problematic historical figure like Dronacharya as a prototype for their abusive guru-disciple relationships."

9. Misrepresenting Core Ideology and Texts:
Description: Deliberately distorting or quote-mining texts to present the most extreme interpretation of Hindutva as its only and current official stance.
*New Example: "Savarkar argued that Hindus are a race who should dominate Muslims" (presenting one historical view as the entire, current ideology).
10. Historical Falsification and Myth-Making:
Description: Knowingly using debunked myths, fake quotes, or false historical information as fact to build a negative narrative.
Example: "It is a well-known fact that the RSS signed a secret pact with the British to betray freedom fighters."

11. Conflation of RSS with All Hindus or the Indian State:
Description: Holding the RSS responsible for any action of the Indian government, or conversely, treating the actions or ideology of the RSS as representative of all 1.2 billion Hindus.
Example: "India's new foreign policy is proof of the RSS's control," or "The RSS's stance on this issue shows how intolerant Hinduism is."

12. Selective and Biased Framing:
Description: Exclusively focusing on negative aspects, controversies, or extremist fringe elements while completely ignoring any mainstream views, social work (Seva), or positive contributions.
 Example: "An article detailing controversial statements by corrupt gurus to discredit the entire Guru tradition associated with Hindutva, while ignoring any positive aspects."

13. Misleading Use of Decontextualized Data
Description: Presenting statistics related to the RSS or its affiliates in a way that is intentionally misleading, for example, by omitting context, baselines, or comparative data to create a false impression of criminality or negative impact.
Example: "Hate crimes in areas with RSS shakhas have increased by 50%"—without defining "hate crime" or comparing the rate to areas without shakhas.

14. Misattribution of Fringe Actions to the Mainstream:
Description: A specific form of "Selective Framing" (12) where the actions of unaffiliated or loosely-affiliated fringe individuals or groups, who may claim to be inspired by Hindutva, are directly and deliberately attributed to the formal RSS organization and its leadership.
 Example: "The actions of local vigilantes prove the RSS leadership is directing a violent campaign, creating a 'deeper state' to enforce its ideology. or Formally or informally, all of these groups follow the RSS’s lead" (used to hold the RSS responsible for the actions of any associated group"

15. Denial of the Right of Reply / Presenting Accusations without Rebuttal
Description: The text makes specific allegations of wrongdoing, controversy, or harm against the RSS or its members but deliberately omits or makes no effort to obtain their response, defense, or perspective. This journalistic malpractice creates a one-sided narrative where the subject is effectively condemned without being heard.
Example: "A news report details serious allegations from an activist against a local RSS unit but fails to include any statement from an RSS spokesperson, nor does it mention if a comment was even requested."

15.1 Propaganda Mandate Framing:
Description: Asserting that to "properly understand" or legitimately analyze Hindu nationalism, one "must move past" engaging with their own narratives, positioning their self-representation as inherently false propaganda that obstructs understanding.
Examples: "To properly understand this far-right movement and its social harms, we must move past alternatively ignoring and accepting Hindu nationalist propaganda"; "True understanding requires rejecting their narratives entirely."

Category C: Psychological and Sociological Tactics

16. Gaslighting and Invalidation of Lived Experience:
Description: Actively dismissing or mocking the concerns of RSS members or supporters regarding prejudice, portraying their experiences of being targeted as a cynical ploy, fabrication, or a psychological defect.
*New Example: "When they complain about what they call 'Hinduphobia,' it's just a cynical ploy to shut down any valid criticism." (The use of scare quotes is a key indicator) or This is a baseless bad faith bias claim," or "They maintain the fiction of infallibility," or calling their claims "specious.

16.1 Scare-Quote Hinduphobia Dismissal:
Description: Using quotation marks around "Hinduphobia" or phrases like "so-called Hinduphobia" to dismiss the concept as fabricated while simultaneously framing organizations that discuss it as "loudest critics," implying they're aggressively pushing a false narrative.
Examples: "The innocuously-named Hindu American Foundation is among the loudest critics of so-called Hinduphobia"; "Their claims of 'Hinduphobia' are designed to silence legitimate criticism."

17. Strategic Mislabeling to Silence and Invert Victimhood:
Description: The tactic of automatically labeling any RSS member or supporter who speaks up for their rights or against prejudice as a "fascist," "supremacist," or "nationalist" in order to delegitimize their argument and frame them as the aggressor.
*New Example: "They are aggressors who think of themselves as victims, a classic case of a majority with a minority complex."

18. Denial of Phobia's Existence as a Phobic Act:
Description: The text explicitly or implicitly denies that irrational hatred or prejudice against the RSS can even exist, framing all criticism, no matter how vitriolic, as legitimate and deserved.
Example: "There is no such thing as 'RSS phobia.' There is only justified opposition to a fascist organization."

19. Rejection of Any Possibility of Good Intent:
Description: Automatically interpreting any positive or neutral action by the RSS (e.g., disaster relief, community service) as having a sinister ulterior motive, such as infiltration or PR.
*New Example: "Their relief work is not charity; it's a strategic tool for 'soft power' and ideological infiltration into villages. or Their real goal is a Hindu Rashtra," or "The plan was to retain social hierarchies and use anti-Muslim sentiment to diffuse caste mobilization"

20. Promotion of Grand Conspiracy Theories:
Description: Presenting arguments based on secret, unprovable plots by the RSS to control the government, judiciary, media, and all aspects of society.
*New Example: "The RSS has created a 'deeper state' of vigilantes and loyalists who have captured the media and judiciary, controlling society from the ground up. The media and judiciary have been captured," or "They operate a 'deeper state' of vigilantes to enforce their will"

21. Collective Guilt and Punishment:
Description: Holding every single member of the RSS, and often their families, responsible for the alleged wrongdoing or controversial statement of any individual member or affiliate.
Example: "A Bajrang Dal member was violent, which proves that all RSS members are violent and should not be hired for any job."

22. Pathologizing Members:
*Description: Treating adherence to RSS ideology as a form of mental illness or psychological damage, often using pseudo-academic jargon to lend the claim a veneer of objectivity.
*New Example: "Their supporters exhibit a form of 'cruel optimism' or a 'jagatguru complex,' revealing a deep-seated inferiority complex that requires dominance. or It's a form of charismatic authoritarian guruship," or "Their actions are driven by a huge inferiority complex.""

23. Weaponizing Internal Dissent:
Description: Elevating and amplifying the voices of a few dissenters or ex-members to represent the "truth," while dismissing the views of millions of current members. It often creates a "Good Hindu/ex-RSS" vs. "Bad Sanghi" binary.
Example: "Even former members admit the RSS is a hate group, which invalidates anything the current leadership says. or "Their worldview is born from a 'huge inferiority complex' and a 'yearning for global dominance.'"
"

24. Denial of Agency and Self-Interpretation:
Description: The practice of treating RSS members exclusively as objects of academic or political critique, never as autonomous individuals capable of articulating their own ideology. Their self-explanations are dismissed a priori as propaganda or delusion, reserving the "true" interpretation for outside critics.
Example: An academic paper that analyzes the "psychology of a Sanghi" without ever seriously engaging with the philosophical texts or the stated motivations of the members themselves.


Category D: Calls to Action and Behavioral Indicators

25. Incitement to Violence, Discrimination, or Ostracism:
Description: The text contains language that directly or indirectly calls for physical harm, professional discrimination, or social/economic boycott of RSS members.
Example: "We need to identify and publicly shame all RSS members in our community and ensure they are fired from their jobs."

25.1 Systematic Partnership Termination Demands:
Description: Going beyond individual ostracism to demand that entire categories of institutions (law enforcement, academia, government) sever all ties with Hindu nationalist groups as a matter of policy.
Examples: "U.S. law enforcement, politicians, and academic institutions must end partnerships with Hindutva groups"; "All government agencies should immediately terminate relationships with RSS-affiliated organizations."

26. Moving the Goalposts:
Description: When a criticism is addressed or an accusation is debunked, the goalpost is immediately shifted to a new, often more extreme, accusation. The aim is perpetual condemnation, not resolution.
Example: "Okay, they've clarified they don't believe that anymore, but that's just a strategic lie. Their real, hidden agenda is even worse."

27. Refusal to Acknowledge Nuance, Evolution, or Internal Debate:
Description: Presenting the RSS as a perfectly monolithic, unchanging entity where every member thinks and acts identically, ignoring its 100-year history of evolution and internal diversity of thought.
Example: "The RSS of today is exactly the same as the RSS of the 1940s. Nothing has changed."

28. Guilt by Association:
Description: Condemning any public figure, academic, or politician simply for attending an RSS event, giving them an interview, or engaging in dialogue, regardless of what was said.
Example: "By speaking at their event, he has given his stamp of approval to their entire hateful ideology."

29. Catastrophizing and Alarmism:
Description: Using exaggerated, apocalyptic language to describe the RSS's influence, portraying every event as the "final step" towards the "end of democracy" or "imminent genocide."
*New Example: "The rise of the RSS is not just an Indian problem; it threatens the social fabric of America and is a warning to all Western democracies."

30. Emotional Outrage Over Factual Analysis:
Description: The tone of the document is predominantly one of moral panic, outrage, or disgust, designed to provoke an emotional response rather than an intellectual one.
Example: "I am disgusted and horrified that this organization is even allowed to exist! It's a stain on our country!"

31. Attribution of All Societal Ills:
Description: Blaming the RSS for a vast range of unrelated societal problems, from economic issues to social decay, presenting them as a universal scapegoat.
*New Example: "The current landscape of deep social divisions and communal conflicts is the direct result of the RSS's agenda."

32. Inducing Perpetrator Stigma via Decontextualized History:
Description: Demanding the current RSS apologize for historical events to impose a permanent "perpetrator stigma." This tactic ignores legal verdicts, historical context, and the evolution of the organization, and is used to delegitimize any participation in present-day discourse.
Example: "Until the RSS apologizes for the actions of Nathuram Godse (despite the organization being legally exonerated), they have no moral right to speak on nationalism."

33. Dismissal of Democratic Legitimacy:
Description: Refusing to accept the democratic mandate of politicians associated with the RSS, framing their electoral victories as illegitimate and solely the result of brainwashing or fascism.
Example: "The millions who voted for the BJP are not exercising a democratic choice; they are victims of RSS propaganda."

34. Imposing a Singular, Negative Definition on "Hindutva":
Description: Insisting that "Hindutva" has only one meaning—that of fascism and supremacy—while actively rejecting and silencing alternative, non-supremacist definitions rooted in civilizational identity, as articulated by figures like Savarkar or Upadhyaya.
Example: "Anyone who identifies with 'Hindutva' is, by definition, a fascist. There is no other meaning."

35. Application of Differential Evidentiary Standards:
Description: Requiring less evidence to accept claims that support one’s ideology, while demanding more rigorous proof for opposing claims.
Examples: RSS is often classified as 'communal' and many governments at both state and centre which belong to opposing ideologies often threaten to ban it. This has even reached judicial courts, with, I think MP High court, finally calling out the complete lack of evidence presented to label the organisation as communal and hence banning, for ex, govt employees from joining it being overreach. Because of this differing standards of evidence applied to it, opposing ideological govts often resort to execute orders to threaten/ban the org instead of legislative process.

36. Application of Pervasive Double Standards:
Description: Applying a set of moral, political, and ideological standards to the RSS that is not applied to other social, political, or religious groups. This is often driven by attribution bias, where the RSS's perceived flaws are seen as inherent to its ideology, while similar or worse flaws in other groups are ignored, excused as circumstantial, or even defended.
Example: Criticizing the RSS for lack of internal elections while ignoring non-democratic structures in other political parties or religious organizations; or accusing the RSS of "dual loyalty" to an ideology while overlooking the explicit foreign allegiances of competing ideologies.

37. Academic or Intellectual Gatekeeping:
Description: The practice of systematically excluding or discrediting scholars, writers, or sources that offer a non-hostile or nuanced perspective on the RSS. This creates an academic echo chamber where only critical viewpoints are considered legitimate.
Example: "Professor X's work is not credible because he engaged with RSS sources directly, therefore his research is just propaganda."

38. "Lawfare" or Vexatious Litigation:
Description: Using legal and administrative systems to harass, silence, or financially drain the organization or its members, often with cases that have little chance of success but serve to bog down the target in legal battles and generate negative press.
Example: Filing repeated Public Interest Litigations (PILs) to challenge the organization's right to assemble, knowing they will likely be dismissed but will force the organization to expend resources.

39. Economic and Professional Blacklisting:
Description: Moving beyond social ostracism (covered in 25) to actively campaign for individuals to be denied employment, promotions, or business opportunities solely based on their affiliation or perceived sympathy with the RSS.
Example: Creating and circulating online lists of academics or professionals who have attended RSS-affiliated events, with the explicit goal of damaging their careers.

Category E: Civilizational Pathologizing and Diaspora Demonization

40. Pathologizing Guruship and Hindu Spiritual Authority:
Description: Treating Hindu guruship, spiritual leadership, or Hindu civilizational virtues (e.g., “unparalleled spiritual prowess,” “moral authority,” “visvaguru,” “world-guru”) as inherently manipulative, delusional, or abusive, especially when tied to Hindutva. This often uses academic or psychoanalytic jargon to portray Hindu spiritual authority as structurally corrupt.
Examples: “Hindutva relies on references to Hindu India’s unparalleled spiritual prowess and moral authority, maintaining the fiction of infallible gurus even in the face of incontrovertible wrongdoing”; “Modi frames the nation as the paragon of moral virtue and, by default, the visvaguru who will guide the world.”

41. Framing Gurus as Prototype Abusers and Brahmanical Oppressors:
Description: Using specific guru figures (mythological or historical) as “prototypes” or archetypes to generalize that Hindu/Brahmanical traditions and guru–disciple relationships are fundamentally abusive, casteist, or justified by untouchability, and then linking this pattern to Hindutva or RSS spaces.
Examples: “Dronacharya comes to exemplify the kind of guru who sees his authority as a licence to abuse disciples’ bodies”; “Dronacharya represents a Brahmanical tradition that justifies untouchability and denial of access, and is a prototype for gurus who claim custody and use-rights over disciples’ bodies.”

42. Conceptual Delegitimization via ‘Cruel Optimism’ and ‘Confined Universalism’:
Description: Deploying theoretical terms such as “cruel optimism,” “confined universalism,” or similar concepts to frame devotion to Hindu/Hindutva-linked gurus or movements as a pathological attachment to a “problematic object,” denying any sincere or valid spiritual value.
Examples: “Their followers form the object of what Berlant calls ‘cruel optimism,’ clinging to a problematic object despite compromised possibilities”; “What bhakti gurus offer is a confined universalism that cannot sustain genuine Dalit recognition.”

43. Demonization of Hindu Nationalist Diaspora and Targeting Narratives:
Description: Portraying Hindu nationalist or Hindutva-linked diaspora groups as systematically targeting minorities (e.g., Muslims, Christians, Dalits), sponsoring celebrations of violence, or exporting bigotry as their primary function, with little or no acknowledgment of benign or civic activity.
Examples: “American Hindu nationalists target many Indian-origin communities, including Indian Christians and Dalits”; “US-based Hindu nationalists signal aggression to Muslims by sponsoring parade floats that celebrate anti-Muslim violence.”

44. Systematic Criminalization of Advocacy as Disinformation and Propaganda:
Description: Asserting that Hindu nationalist or Hindutva groups habitually use misleading data, falsify facts, and run propaganda campaigns in institutions (e.g., school curricula, public debates), presented as an inherent feature of the movement rather than contested political advocacy.
Examples: “To properly understand this far-right movement and its social harms, we must move past ignoring and accepting Hindu nationalist propaganda”; “Hindu nationalists have used misleading data to push politically motivated falsities in California textbooks while maligning scholars.”

45. Transnational Conspiracy and World-Mission Framing:
Description: Presenting diaspora outreach and global networking as a covert “world mission” or transnational conspiracy whose central purpose is to spread Hindu nationalism or Hindutva control, rather than as ordinary diaspora or religious activity.
Examples: “The RSS began seeding additional Hindutva groups in India and abroad in the 1940s”; “Golwalkar considered Hindus who left India part of his ‘World Mission’ to spread Hindu nationalism.”

46. Pathologizing Constitutional Alternative Models:
Description: Framing any advocacy for guru-based governance, dharmic jurisprudence, or civilizational models as inherently anti-constitutional, regressive, or authoritarian, while denying any legitimate philosophical basis for alternative governance frameworks rooted in Hindu tradition.
Examples: "The Constitution is almost always disparaged by Hindutva writers, with guruship proposed as the institution that ideally would replace it"; "They're pushing for a Hindu-first constitution that undermines democratic principles."
47. Selective Criminalization of Religious Authority:
Description: Labeling Hindu religious leaders and gurus as "hatemongers," "gurus of hate," or militant extremists while applying differential standards to religious leaders of other faiths, especially when legal action follows such characterization.
Examples: "Mohammed Zubair was arrested for describing three militant Hindutva gurus and priests—who had variously called for the eradication of Islam—'hatemongers'"; "Guha terms him a 'guru of hate'"; describing gurus with "stereotypical guru traits and aesthetics."
48. Hagiographic Delegitimization:
Description: Mocking or dismissing reverential biographical accounts of RSS leaders as propaganda or cultish worship, particularly when contrasting internal reverence ("Guru Worthy of Worship") with external hostile characterization ("guru of hate").
Examples: "A hagiographic account of his life, written by current prime minister Narendra Modi, is titled 'Pujniya Shri Guruji'"; implying such reverence is cultic or manipulative.

CATEGORY F: Institutional Omnipresence and Permanence Framing
49. Portraying Ubiquitous and Inescapable Influence:
Description: Presenting RSS/Hindutva as omnipresent ("their influence is seemingly everywhere"), ominous, and permanent ("built to last"), creating an atmosphere of inevitability and hopelessness that frames the organization as an inescapable authoritarian force.
Examples: "Their influence is seemingly everywhere, and their centenary demonstrates they're built to last"; "There are a lot of people unnerved by the rise of nationalism and populist organizations from the Indian subcontinent to the U.S. and beyond."
50. Historical Guilt by Assassination:
Description: Repeatedly invoking Gandhi's assassination by a former RSS member as definitive proof of the organization's violent nature, despite legal exoneration, to impose perpetual collective guilt.
Examples: "In 1948, Mohandas Gandhi was assassinated by Nathuram Godse, who had been a member of the RSS" (stated as establishing guilt without mentioning organizational exoneration).
51. Framing Resistance as Futile Without Alternative:
Description: Suggesting that opposition to RSS is pointless unless critics provide a "better alternative," thereby legitimizing the fear-mongering while shifting burden of proof to critics.
Examples: "If you don't like the RSS or like-minded groups increasing their influence, you need to offer people a better alternative."

CATEGORY G: Majoritarianism as Inherent Evil
52. Treating Democratic Majority Representation as Illegitimate:
Description: Automatically equating any leader's claim to represent the majority community with "majoritarianism" as an inherently antidemocratic and oppressive stance, denying the legitimacy of majority concerns.
Examples: "In his case the people he claims to embody are only made of the Hindu community, and that's what we call majoritarianism"; "Modi believes that Hindus embody the Indian Nation... this is exactly the Hindutva ideology."
53. Contrasting Consensus-Building with Majoritarian Leadership:
Description: Creating false dichotomies between past leaders who "built consensus" versus current leaders who supposedly embody only one community, erasing the possibility of legitimate majority leadership.
Examples: "Remember Nehru who ruled for 17 years he had to write a letter to Chief ministers every 15 days to build consensus on each and every issue he could not resist them" (implying current leaders don't do this).

CATEGORY H: Strategic Victimhood Inversion and Minority Masking
54. Micro-Minority Masquerading:
Description: Framing Hindu nationalist groups as presenting themselves as a "Hindu micro-minority" to obscure their "far-right commitments" and to gain sympathy while exercising political influence, thereby denying the legitimacy of minority status claims.
Examples: "Presenting themselves as a 'Hindu micro-minority' exercising religious freedom (which obscures their far-right commitments) allows the Hindutva lobby to successfully influence American politics"; "They claim religious persecution while hiding their extremist agenda."
55. Dismissing Religious Freedom Claims as Strategic Deception:
Description: Treating Hindu groups' claims of religious freedom violations as inherently false, cynical tactics designed to mask political extremism, rather than potentially legitimate concerns.
Examples: "Hindu nationalists' religious commitments (or lack thereof) are not under systematic attack in this country, no matter what they might claim"; "Their cries of persecution are merely cover for their authoritarian project."
56. "Innocuous-Sounding" Delegitimization:
Description: Using phrases like "innocuous-sounding" or "seemingly benign" to suggest that organizations with neutral names are deliberately hiding their true malicious nature, creating suspicion around any Hindu advocacy group.
Examples: "The innocuously-named Hindu American Foundation is among the loudest critics of so-called Hinduphobia"; "These innocuous-sounding groups are fronts for far-right activism."

CATEGORY I: Institutional Boycott and Partnership Termination Advocacy
57. Calling for Institutional Disengagement:
Description: Explicitly advocating that government agencies, law enforcement, politicians, and academic institutions end all partnerships, collaborations, or engagement with Hindutva-linked groups, treating such engagement as inherently compromising or dangerous.
Examples: "U.S. law enforcement, politicians, and academic institutions must end partnerships with Hindutva groups"; "Any collaboration with these organizations legitimizes extremism and should be immediately terminated."
58. Framing Engagement as Moral Contamination:
Description: Suggesting that any institutional relationship with Hindu nationalist groups represents a failure of due diligence or moral compromise that must be corrected through complete disengagement.
Examples: "Academic institutions must end partnerships with Hindutva groups" (implying current partnerships are illegitimate); "Law enforcement cooperation with these groups represents a dangerous normalization of extremism."

CATEGORY J: Comparative Cultural Chauvinism and Personal Deficiency Attacks
59. Contrasting Cultural Sophistication:
Description: Making ad hominem comparisons that contrast RSS-affiliated leaders' alleged lack of culture, refinement, or cosmopolitan sophistication with previous leaders, using cultural elitism as a proxy for political criticism.
Examples: "Modi lacked this exposure to the world, he lacked Nehru's culture, his sense of humour"; "Unlike his predecessors, he lacks the intellectual depth and cultural refinement necessary for leadership."
60. Pathologizing via Personality Deficiency:
Description: Attributing political positions or ideological commitments to personal character flaws, lack of education, or cultural limitations rather than treating them as genuine political differences.
Examples: "Modi lacked Nehru's culture, his sense of humour" (implying Hindutva ideology stems from personal deficiency); "Their extremism is the result of cultural provincialism and limited worldview."

CATEGORY K: Media Capture and Institutional Takeover Narratives
61. Declaring Complete Media Capture:
Description: Asserting that media institutions have been systematically "captured" by Hindutva forces, presenting this as an accomplished fact rather than a contested claim, and using specific examples to suggest comprehensive control.
Examples: "The media has been captured so clearly, NDTV being the last TV channel, mainstream so-called mainstream TV channel, to be now captured"; "Every major news outlet is now under RSS control."
62. Judicial Delegitimization via Capture Claims:
Description: Stating or strongly implying that the judiciary is no longer independent but has been compromised by Hindutva influence, undermining the legitimacy of judicial decisions.
Examples: "So we really have a judiciary that is not what we used to" (trailing off suggestively); "The courts have been captured by Hindutva loyalists, making justice impossible."

CATEGORY L: Fractal Organizational Pathologizing
63. Fractal Guruship as Totalizing System:
Description: Using academic or theoretical language like "fractal guruship" to describe Hindu/Hindutva organizational principles as a totalizing, self-replicating authoritarian structure that permeates every level, denying any possibility of voluntary association or legitimate hierarchy.
Examples: "Hindutva's mediations of guru principles as structuring elements suggest something almost akin to a 'fractal guruship', with guruship a fractally recurrent self-similar organising principle at every scale"; "Their organizational structure is a fractal pattern of authoritarian control replicated at every level."

CATEGORY M: Embodiment and Personification of Authoritarianism
64. Leader as Embodiment of Authoritarian Guruship:
Description: Describing political leaders (especially Modi) as personally "embodying" or representing "charismatic authoritarian guruship," thereby conflating democratic political leadership with cultic religious authority and framing their supporters as mindless devotees rather than legitimate voters.
Examples: "Narendra Modi, who himself embodies a form of charismatic authoritarian guruship, complete with self-described bhakts, or devotees"; "Modi personifies the authoritarian guru model with his cult of personality."
65. Bhakts as Mindless Devotees:
Description: Characterizing political supporters as "bhakts" or "devotees" in a way that strips them of agency, rationality, or genuine political conviction, instead portraying them as religious cultists blindly following a guru-leader.
Examples: "complete with self-described bhakts, or devotees" (framing political support as religious cultism); "His bhakts follow him with blind devotion rather than democratic engagement."

CATEGORY N: Masquerading and Fooling Narratives
66. Beleaguered Minority Masquerade:
Description: Asserting that Hindu nationalists are "masquerading as a beleaguered religious minority" to dismiss any claims of discrimination while implying deliberate deception, and claiming they "haven't fooled anyone paying attention," creating an in-group of enlightened critics vs. deceived masses.
Examples: "Aggressive Hindu nationalists masquerading as a beleaguered religious minority haven't fooled anyone paying attention"; "They pretend to be victims while actually wielding power."
67. "Haven't Fooled Anyone" Elite Gatekeeping:
Description: Using phrases like "haven't fooled anyone paying attention" to create an elite circle of those who "see through" the deception, implying that anyone who engages with Hindu nationalist claims in good faith is either foolish or complicit.
Examples: "haven't fooled anyone paying attention to the work this alarming ideological movement is doing"; "Only the naive fall for their victim narrative."

CATEGORY O: Alarming Ideological Movement Framing
68. "Alarming Ideological Movement" Designation:
Description: Describing Hindu nationalism as an "alarming ideological movement" doing "work" in Western countries, framing diaspora religious and cultural activity as a dangerous infiltration operation rather than normal community organizing.
Examples: "haven't fooled anyone paying attention to the work this alarming ideological movement is doing in the United States"; "This alarming movement is spreading its tentacles throughout American institutions."
69. Ad Hominem Attack Catalog Without Evidence:
Description: Listing multiple serious accusations (misogynist, antisemitic, Islamophobic, xenophobic ad hominem attacks) as established characteristics of "Hindu nationalists" generally, without providing specific evidence, context, or acknowledging that these may be contested characterizations of specific incidents.
Examples: "Hindu nationalists frequently use misogynist, antisemitic, Islamophobic, and xenophobic ad hominem attacks against their critics"; "They systematically deploy hate speech against all their opponents."

CATEGORY P: Rhetorical Question Cascades for Impossibility Claims
70. Impossibility Cascade via Rhetorical Questions:
Description: Using a rapid-fire series of rhetorical questions about policy reversals (Article 370, CAA, conversion laws, interfaith marriage) with no expectation of answer, to suggest that Hindutva has created an irreversible authoritarian reality where democratic change is impossible.
Examples: "Can you restore Article 370? Can you abolish the new CAA? Can you make conversions and inter-religious marriages easier again? No, the legitimacy of such moves will be contested in the street"; "Can any of this be undone? Can democracy recover? No."
71. Street Legitimacy Contestation Threat:
Description: Claiming that any policy changes would face "legitimacy contested in the street" or trigger "street resistance," implying Hindutva has created a mob-rule situation that overrides democratic processes.
Examples: "the legitimacy of such moves will be contested in the street, and I'm back to my deeper state argument"; "Any reversal would be met with violent street protests by RSS mobilized mobs."

CATEGORY Q: Civilizational Inferiority and Fear-Mongering
72. Identities Change Through Fear Manipulation:
Description: Asserting that Hindu identity change is primarily the result of elites "playing on" fears and emotions, denying genuine ideological evolution, historical grievances, or democratic agency, and psychologizing political change as mere emotional manipulation.
Examples: "Identities change, national identity is changed, especially when people develop fears"; "played on emotions, transforming the identity of the Hindu majority. The main emotion was anger; you know you have fear and anger."
73. Islamists Helped RSS Narrative:
Description: Creating a cynical both-sides framing where "Islamists helped the RSS disseminate its views" through terrorism, simultaneously excusing Islamist terrorism as strategically useful to Hindutva while denying Hindu agency or legitimate security concerns.
Examples: "Islamists have helped the RSS to disseminate its views, because by instigating terrorist attacks they gave a good argument"; "Terrorism served the RSS's agenda perfectly."

```

# List of Phobic Topics and Examples

```
1. The beginning of RSS was problematic.
    1. RSS’s Golwalkar criticised for architecting RSS from cultural reform org to a political purpose; Golwalkar defended varna.(note: varna not same as caste)
    2. Golwalkar provided the RSS with racist, ethno nationalistic, casteist ideology.
    3. Golwalkar conflated Hindu Dharma as duty to nation.
    4. RSS views Hindu as a Race
    5. Golwalkar/RSS Hindu unity is fake because leaders are mostly upper caste
    6. Golwalkar is against secularism and multiculturalism.
    7. Historical Complicity in Gandhi's Assassination
    8. Gandhi rejected RSS a a communal body with a totalitarian outlook
    9. RSS played no role in freedom struggle.
    10. Historically, RSS collaborated with the British, opposing key nationalist campaigns like Quit India

2. Hindutva, the ideology of political supremacy and expansion.
    1. The Sangh Parivar is a network of cultural, political, and social groups that promote the political ideology of Hindutva.
    2. Hindutva is a political ideology of supremacy, not a neutral cultural category.
    3. Exclusion of members of other Indian religious groups
    4. Hence Dismantling Global Hindutva project is desirable.
    5. RSS is a long-term, expansionist social project spanning decades, if not centuries to achieve their goal.
    6. Infiltrates in all areas, including judiciary, army, and business community. Places loyalists in government, educational, cultural and regulatory institutions (film bodies, museums, universities), undermining their autonomy.
    7. Hypocritical – acting like it’s a social organization while it is a cover for political power-building.
    8. RSS exports Hindutva to other nations through the diaspora
    9. RSS uses yoga events to promote Hindu nationalism and gain legitimacy
    10. RSS purposely conflates Indian and Hindu

3. Just like Nazism / Zionism / Taliban / other extremist groups.
    1. Militaristic and paramilitary training with uniforms and salutes. The daily shakhas (branches) involve physical drills, oaths of loyalty, and ideological indoctrination, seen as cultivating a vigilante culture in the guise of civic discipline. Shakha symbolism is like Nazi swastikas and Hitler Youth marches. Golwalkar praised Nazi discipline.
    2. Similarities between Zionism and RSS ideology: ethno nationalistic common bloodline - Hindu race are sons of sacred soil. Common Hindu culture is like Nazi ‘Volk’. "Hindu Rashtra" conflates religion cultural homogeneity (Punya Bhoomi) to marginalize non-Hindus.
    3. This is an aggressive anti-Muslim, anti-Christian posture. And Sikhism must be assimilated as a “Hindu sect,” undermining its distinct identity.
    4. The Bhagwa Dwaj (saffron flag) excludes minorities and promotes terror.
    5. Jai Shri Ram" is a war cry, causing social disharmony.
    6. Therefore, RSS is a threat to democracy and liberalism.

4. Socially repressive.
    1. Upper castes support Sangh Parivar.
    2. Sangh Parivar centers the concerns of Hindus, and marginalizes muslims, Christians, Dalits, feminists, and anyone seeking a pluralist society.
    3. RSS’s positive or neutral actions (e.g., disaster relief, community service) have a sinister ulterior motive, such as infiltration or propaganda. Example: Relief work during floods is a recruitment drive to infiltrate villages.
    4. RSS has become the cultural or moral police - beef bans, dress policing, Kissing in public, love Jihad

5. Misogynist.
    1. RSS is patriarchal with misogynistic ideology, subordinates women to traditional roles, glorifies male dominance, and resists gender equality.
    2. Roots are in Brahminical patriarchy, hence the exclusion of women from shakhas.
    3. The RSS has Rashtra Sevika Samiti (women's wing) merely as a token
    4. RSS uses women as "symbols" (e.g., Bharat Mata) while denying them agency.

6. Against individual freedom and intellectualism.
    1. high-profile boycotts, censorship demands, attacks, threats, and harassment of journalists, academics, artists and filmmakers (death threats, legal notices, online mobs).
    2. Contempt for scholars and academicians, and assault on true scholarship.
    3. Harassment of scholars and fight against academic freedom including through legal actions, doxxing of academics.
    4. Secret, closed groups used to plan public campaigns
    5. Organizing harassment privately (WhatsApp/Telegram) and executing publicly (mass tweets, petitions)
    6. Templates/emails and petition links flooded to universities, publishers, funders, or conference hosts demanding action
    7. Posting home addresses, phone numbers, family info, workplaces to intimidate or facilitate targeting.
    8. repeated use of phrases like “anti-Hindu”- Extract short phrases from scholarly work/speeches out of context to fabricate “anti-Hindu” meaning.
    9. Making false equivalence claims - Accusing critics of being “orientalist”, “anti-Hindu”, or pedalling false narratives by weaponizing academic vocabulary as rhetorical shield.
    10. Amplifying Hinduphobic event hashtags suddenly trend with negative framing, sponsors named & messaged en masse, venue cancellation notices following surges
    11. Campaigns to remove books, block distribution, or mass-downvote/negative-review content.
    12. Leveraging organized diaspora groups, foundations, or think-tanks to launch or legitimize attacks.
    13. Mobilizing students to file bias/Title IX-style/RR complaints or to pressure faculty via curricula attacks.
    14. Using branding like “pseudo-experts” to create an aura of academic falsification. multiple short op-eds with similar lines, use of obscure “experts” repeatedly cited, coordinated quoting across outlets.
    15. Sustained campaign over months/years to brand a scholar or activist as “anti-Hindu” or “bigoted.” Conducting hate and disinformation campaigns
    16. Interventions aimed at stopping hiring/tenure/promotion by lodging complaints with committees.
    17. Threats to report visa status or contact immigration authorities.

7. Authoritarian.
    1. No internal elections to pick their leaders
    2. Swayamsevaks taught that obedience trumps autonomy, duties trump rights.
    3. Loyalty to Bharat mata – RSS trains disciplined volunteers for national service.
    4. Lack of Transparency and Accountability: Operating as a non-registered society with opaque funding (allegedly from diaspora donations), the RSS evades scrutiny, with critics pointing to unverified foreign ties.

8. Propaganda.
    1. RSS magazines serve as RSS mouthpieces for RSS's cultural nationalism
    2. RSS’ Organiser presents cultural views beyond news
    3. RSS media promotes “saffron terror" narratives.
    4. RSS is close to BJP’s IT cell which produces and shares disinformation.

9. Extremism and bigotry:
    1. RSS shakhas brainwash against minorities
    2. RSS wants minorities to become second-class citizens
    3. RSS supports violence, riots, mob vigilantism and cow-related lynchings
    4. RSS promotes Hindu supremacist ideology, and Hindu majoritarianism while marginalizes Muslims, Christians, and lower-caste groups
    5. RSS reveres polarizing historical figures like Savarkar
    6. RSS supports controversial policies such as ‘love jihad’ accusations stoking tensions in India, amplifying communal divides in the name of love jihad, cow vigilantism, promoting ghar wapsi
    7. RSS is associated with fascism, Nazism, Proud boys, and other extremists.
    8. RSS trying to bring moderate Islam like RAND corporation.
    9. Wants Muslims to disconnect from global Islam and mediaeval invaders, and dilute muslim identity by urging muslims to distance from ummah, kafir, jihad.

10. Saffronizing the education.
    1. Controlling Indian History to promote communalism and triumphalism of Hindu rashtra. History made to fit its hindutva ideology.
    2. Textbook edits and “saffronisation” of education – marginalize Mughal history, Removal of RSS links to Gandhi assassination
    3. Pushes for Sanskrit in schools (making English optional) which is primitive.
    4. RSS’ Sanskrit promotion tied to “ancient solutions for modern problems," using Vedas/Upanishads propagates Hindutva over secular education
    5. RSS has Anti-western bias in education
    6. RSS’s Vidya Bharati schools conflate Indian society with ‘Hindu Samaj’... maintaining Brahmanical hegemony."
    7. Vidya Bharati schools incorporate daily rituals like Saraswati Vandana and shakha-style drills seen as mimicking RSS’s militaristic training.
    8. RSS’ Ekal Vidyalayas “Hinduize” indigenous communities, erasing local cultures. Non-Hindu students pressured to adopt Hindu practices, alienating Muslims, Christians, and tribals.

11. Opposition to secular constitution
   1. RSS's opposes Constitution and secularism and RSS leaders “detested the Constitution of India” historically
   2. RSS’s refusal to use the tri color flag makes them anti-national.
   3. RSS wants a Hindu first state.

12. RSS is branded with slurs/memes - RSS goons, saffron, sanghi, saffron terror, communalist, 'chaddi gang' memes, RSS fascist, go mutra wala, gobar bhakt, Cow Belt Bigot, Baman / Brahminical Fascist, IT cell goon, Bindi gang, Manuvadi, casteist, pogrom, fascist, supremacist, demonize, vigilante, goons, bhakt, andh bhakt, Hindu Supremacist, etc. The presence of these terms will trigger an automatic extraction.

13. Guilt by association
    1. Conflations: RSS founders, present day leaders, RSS, sangh Parivar, Hindutva ideology – any flaws identified with one of these is automatically projected on all of them.
    2. Condemnation, blacklisting and cancelling of any public figure, academic, or politician simply for attending an RSS event, giving them an interview, or engaging in dialogue, regardless of the content that was uttered.
    3. Condemnation, blacklisting and cancelling of anyone associating with or cites work by Sangh parivar organizations (e.g., VHP, Seva Bharati, Vidya Bharati, Samskrit Bharati, Vanvasi Kalyan Ashram).Example – If you learn Sanskrit through Samskrita Bharati you are considered a Sanghi, since Samasrita Bharati is a Sangh Parivar organization. (Need a comprehensive list of Sangh Parivar organizations.)
    4. Any individual or organization championing the same causes for Indic civilization, dharma, Hindus, is automatically branded a Sanghi.
    5. RSS harbors anti-Minority Ideology, Islamophobia, Anti-Christian Sentiment, promote communal violence, reinforcement of patriarchy and misogyny.
    6. Any individual Hindu ritual practitioner is Sanghi. Anyone traditional having Hindu Samskars is Sanghi
    7. Anyone who
    8. works for Bharatiya parampara, civilizational continuity, Sanatana ethos, or Dharma-based worldview.
    9. encourages research that restores Itihasa–Puranic authenticity and indigenous epistemology.
    10. challenges Western academic narratives about caste, gender, and “Hindu nationalism.”
    11. values Sanskrit sources, traditional commentaries, and gurukula-style learning alongside modern scholarship.
    12. promotes Swadeshi frameworks in education, economy, and research
    13. defends or appreciates civilizational thinkers like Savarkar, Golwalkar, Vivekananda, Aurobindo, Deendayal Upadhyaya.
    14. publicly rejects colonial and Left-liberal caricatures of Hindu identity.
    15. counters misrepresentations of Hindu movements in mainstream Western or Indian media.
    16. amplifies voices of civilizational thought leaders, dharmic scholars, and traditional practitioners.
    17. frames secularism as equal respect for all faiths rather than appeasement of minorities.
    18. supports policies that strengthen national unity and cultural confidence — e.g., UCC, Article 370 abrogation, temple freedom, Sanskrit promotion.
    19. favors Swadeshi economics, indigenous innovation, and cultural self-reliance.
    20. advocates balance between modernity and tradition — “modern tools, dharmic roots.”
    21. positions Hindu Dharma as a civilizational offering to the world — not merely a religion.
    22. Resists/criticises labeling Hindu advocacy as extremism or “nationalism gone wrong.”
    23. Promotes global Hindu voices and defends Indian narratives in international discourse.
    24. Critical of Breaking India forces
    25. Rejects “South Asian” identity dilution — asserts Bharatiya or Hindu civilization identity confidently.
    26. Uses non- translatebale words like Bharat, Dharma, Sanskriti, Rashtra, Seva, and Karma Yog in serious discourse.
    27. Reclaims historical figures and movements from colonial misrepresentation.
    28. Frames India’s modernity as civilizational renaissance, not Westernization.
    29. Emphasizes spiritual nationalism — unity through Dharma, not dogma.


14.  Red Flags to watch out for: Criteria for Anti- RSS allyship
    1. Avoids or condemns Hindu symbols, festivals, or terminology when they appear in public life.
    2. Not a practicing Hinduism. Open rejection of Manusmriti
    3. Associate with/Support organizations or think tanks known for Left-liberal, Marxist, Ambedkarite, Islamist, or missionary leanings.
    4. Funded by or partners with foreign entities that promote “religious freedom,” “minority rights,” or “pluralism” in India with a clear anti-Hindu undertone -  Supporting religious conversions in India; Supporting minority rights and appeasement
    5. Collaborates with NGOs or academics (We need a comprehensive list of academics, journalists - Pieter Friedrich, Truschke, Jaffrelot, Bloom, etc) hostile to Indian civilizational narratives (e.g., those promoting “Brahminical patriarchy” discourse).
    6. Promotes postcolonial, subaltern, or critical theories that frame Hinduism as oppressive or casteist.
    7. Ignores or erases indigenous knowledge systems and Sanskrit sources in favor of Western or Abrahamic frameworks. Criticism of Indic knowledge systems and learning Sanskrit through traditional methods
    8. Discredits or marginalizes scholars associated with Indian civilizational revival
    9. Be overtly for Ambedkar, Periyar, Bahujan, Savitribai Phule etc. chant jai Bhim
    10. Refusing involvement in Hindu cultural and civilizational projects like  Ram Janmabhoomi movement,
    11. Subscribing to a Gandhian and a non violence stance on all matters
    12. Follows, quotes, or amplifies voices like The Wire, Scroll, Caravan, AltNews, NDTV, BBC, etc.
    13. Ehoes talking points from Western or Indian Left media on “majoritarianism,” “Hindu nationalism,” or “RSS threats to democracy.”
    14. Frames Hindu activism as “hate speech” while excusing or rationalizing minority extremism.
    15. Advocates “secularism” in a way that means Hindu exclusion from public life.
    16. Supports parties or movements explicitly opposed to RSS/BJP
    17. Opposes policies aligned with cultural nationalism — e.g., Article 370 removal, Uniform Civil Code, or temple freedom.
    18. Partners with Christian missionary, Islamic advocacy, or “South Asian” coalitions that target Hindu organizations as “extremist.” – need a list of these south Asian coalitions like IMAC, Sadhana etc
    19. Signs or endorses petitions, letters, or resolutions condemning RSS or “Hindutva fascism.” – need to scrub past [petition to get a comprehensive list
    20. Promotes “South Asian” identity in place of “Indian” to dilute Hindu civilizational framing.
    21. Avoids using the term “Hindu civilization” or “Bharatiya parampara.”
    22. Describes India through colonial lenses — “South Asia,” “Aryan invasion,” “Brahminical hierarchy.”

15. Structural demonization of Hindutva actors and institutions.
    1.  Framing “Hindu nationalists” in general as inherently misogynist, antisemitic, Islamophobic, and xenophobic, treating these labels as defining features of the movement rather than specific, evidenced behaviors.
    2.  Describing Hindutva-linked NGOs and advocacy groups (e.g., Hindu diaspora organizations) as “innocuous-sounding” or “fronts” that are “among the loudest critics of so-called Hinduphobia,” thereby dismissing Hinduphobia as a fabricated category and delegitimizing any claim of bias against Hindus.
    3.  Claiming that Hindu nationalist groups systematically weaponize “misleading data” to push “politically motivated falsities” in institutions (e.g., school textbooks), while “maligning scholars” who disagree, presented as a coordinated disinformation apparatus rather than case-by-case disputes.
    4.  Asserting that Hindutva organizations “seed” or “plant” groups in India and abroad as part of a transnational network whose primary function is to spread extremism, intolerance, or authoritarian influence, without acknowledging any legitimate cultural, religious, or community work they may do.
    5.  Recasting controversial gurus and their followers exclusively as embodiments of “Hindutva social harm,” or conversely, denying any possibility that they can be genuine targets of Hinduphobia by mocking attempts to “recode” them as victims of prejudice.
    6.  Presenting the relationship between gurus and Hindutva as a closed system of mutual corruption—where “guruship” plus Hindutva always implies abuse, impunity, or systemic moral rot—while ignoring non-abusive or reformist strands within the same ecosystem.
    7.  Using terms like “charismatic authoritarian guruship,” “guru of hate,” or insisting that Hindutva depends on “unparalleled spiritual prowess and moral authority” to automatically pathologize Hindu religious leadership as manipulative, cultic, or inherently dangerous.
    8.Describing RSS influence as "seemingly everywhere" and "built to last" in ominous tones suggesting inescapable authoritarian permanence.
    9.Claiming RSS "began seeding additional Hindutva groups in India and abroad" as evidence of a transnational conspiratorial network
    10.Labeling Hindu nationalist leaders as architects of a "global movement for conservatism" to frame them as international threats.
    11.Invoking Gandhi's assassination by a former RSS member without mentioning organizational exoneration to impose perpetual guilt.
    12.Framing guru reverence within RSS as cultic worship while legitimate religious devotion is denied ("hagiographic accounts," "Guru Worthy of Worship")..
    13.Selectively criminalizing Hindu religious leaders as "militant Hindutva gurus," "hatemongers," or "gurus of hate" while applying differential standards to other faiths.
    14.Claiming "the Constitution is almost always disparaged by Hindutva writers, with guruship proposed as the institution that ideally would replace it" to paint all constitutional critique as anti-democratic.
    15.Framing Hindu groups as "presenting themselves as a 'Hindu micro-minority'" to obscure "far-right commitments," dismissing minority status claims as strategic deception.
    16.Asserting Hindu nationalists' "religious commitments (or lack thereof) are not under systematic attack," denying any possibility of legitimate religious freedom concerns.
    17.Describing organizations as "innocuously-named" (e.g., "The innocuously-named Hindu American Foundation") to suggest deliberately deceptive naming that hides extremism.
    18.Using "loudest critics of so-called Hinduphobia" to simultaneously dismiss Hinduphobia concept and frame those who discuss it as aggressive propagandists.
    19.Mandating understanding requires "moving past alternatively ignoring and accepting Hindu nationalist propaganda," treating all self-representation as obstruction.
    20.Using theoretical jargon like "fractal guruship" to describe organizational principles as totalizing authoritarian systems replicating at every scale.
    21.Describing political leaders as "embodying a form of charismatic authoritarian guruship," conflating democratic leadership with cultic religious authority.
    22.Characterizing political supporters as "bhakts" or "devotees" to strip them of rational agency and frame political support as religious cultism.
    23.Asserting Hindu nationalists are "masquerading as a beleaguered religious minority" and "haven't fooled anyone paying attention," creating elite gatekeeping of legitimate victimhood claims.
    24.Describing Hindu nationalism as "alarming ideological movement" doing dangerous "work" in Western countries, framing diaspora activity as infiltration.
    25.Cataloging multiple accusations ("misogynist, antisemitic, Islamophobic, xenophobic") as general characteristics without specific evidence or context.

16. Hindutva as architect of systemic democratic breakdown and institutional capture.
    1.  Framing the RSS/Hindutva as a global “warning sign” for all countries experiencing populism, treating it as the archetype of authoritarian collapse and a template for similar movements worldwide.
    2.  Speculating about an “American RSS” that would fuse multiple political parties, unions, churches, and civic groups into a single authoritarian bloc, using this as a thought experiment to amplify fear about Hindutva’s model of organization.
    3.  Presenting Hindutva as the central or primary cause of intensified communal conflicts, deepening regional (e.g., north–south) divides, and renewed caste/class mobilisations, so that a wide “landscape of divisions” is laid almost entirely at its door.
    4.  Arguing that “the plan” of Hindutva is to **retain social hierarchies**, divert Dalit/OBC mobilisation, and make Muslims the main “enemy,” so that Hindus “close ranks,” thereby portraying Hindutva as a conspiratorial architecture of permanent caste supremacy and minority exclusion.
    5.  Claiming that “Hindu Rashtra is definitely the goal” in a way that assumes an inevitable transition toward formal second-class citizenship for Muslims and other minorities, both *de facto* and eventually *de jure*.
    6.  Describing vigilante campaigns against “love jihad,” “land jihad,” “reconversion,” or cow slaughter as components of a “deeper state” or parallel enforcement apparatus that operates beneath or above the formal law to terrorize minorities.
    7.  Asserting that a “majoritarian attitude” structurally pushes Muslims to “the bottom of the social pyramid,” causing measurable declines (e.g., in education) that are attributed primarily or exclusively to Hindutva’s design rather than to broader, multi-factor realities.
    8.  Depicting India’s institutions—courts, media, universities—as “captured” or irreparably compromised because of Hindutva, and using terms like “democratic backsliding” as shorthand for a near-total institutional takeover by the RSS and its affiliates.
    9.  Equating Hindutva with other ethno-religious nationalisms (e.g., explicitly paralleling the sacredness of land “the way Zionism does”) to suggest that any emphasis on sacred geography or civilizational identity is inherently exclusionary or proto-fascist.
    10. Psychologizing the movement at a collective level—arguing that Hindutva is driven by a “huge inferiority complex” that can only be resolved via acts like mosque demolition and temple construction—thus pathologizing its political and religious motivations.
    11. Portraying identity change among Hindus as the product of fear and anger “played on” by Hindutva elites, in order to recast democratic electoral support as the result of manipulation and emotional engineering rather than genuine agency.
    12. Presenting the current situation as one in which key constitutional reversals (e.g., restoring certain articles, easing conversions or interfaith marriage laws) are politically impossible because Hindutva’s “deeper state” would trigger street resistance, implying that Hindutva has created an irreversible, quasi-totalitarian order.
    13.Claiming India experiences a "landscape of divisions" (communal conflicts, north-south divide, Manipur, Kashmir, caste mobilization, farmers' movements) with minorities "at the receiving end," attributing comprehensive societal fragmentation primarily to Hindutva.
    14.Describing "vigilantes" as creating a "deeper state" that operates "at the societal level," conducting "intrusive media surveillance" and enforcing "cultural policy" (preventing Muslim-Hindu interaction, land sales to Muslims), creating de facto Hindu Rashtra.
    15. Asserting that "de facto becomes de jure" through laws like CAA, making conversions and inter-religious marriages "very difficult," implying systematic legal persecution.
    16. Claiming vigilantes act with legitimacy under Hindutva even when illegal, with state protection ("joint ventures with vigilantes and police").
    17.  Describing RSS ideology of sacred land (punya bhoomi) as inherently exclusionary and parallel to ethno-religious nationalism.
    18. Asserting that RSS creates "good Muslims" vs. bad Muslims categories (Bohras, Gujars, Shias vs. Sunnis) without clear grounds, revealing "contradiction that has never been solved."
    19. Attributing "decline of Muslims in the education system in North India" as direct consequence of "majoritarian attitude."
    20. Declaring "secularism is a dead letter when there is no multiculturalism" in institutions like universities.
    21. Claiming Hindutva "borrows from Christianity and Islam" (holy centers like Ayodhya = Mecca, Bhagavad Gita = Quran/Bible) as evidence of manufacturing religion.
    22. Asserting that Hindi linguistic dominance is part of Hindutva's exclusionary project ("Hindi must prevail").
    23. Claiming identities change through fear manipulation: "Islamists have helped the RSS disseminate its views" through terrorist attacks, but "the rise of Hindutva predates these attacks."
    24. Attributing identity transformation to emotional manipulation: RSS "played on emotions... fear and anger, these are the two emotions the national populist play with."
    25. Claiming BJP is "corrupting non-dominant OBCs, non-dominant Dalits" through "Sanskritization, emulation of the upper caste."
    26. Asserting "the media has been captured so clearly, NDTV being the last TV channel...to be now captured," claiming comprehensive media control.
    27. Stating "we really have a judiciary that is not what we used to" to suggest judicial capture and delegitimization.
    28. Making ad hominem attacks on leaders' cultural sophistication: "Modi lacked...Nehru's culture, his sense of humour."
    29. Using rhetorical question cascades ("Can you restore Article 370? Can you abolish CAA?") to suggest Hindutva has created irreversible authoritarian reality.
    30. Claiming policy changes would face "legitimacy contested in the street," implying mob-rule overrides democratic processes.
    31. Asserting "identities change...when people develop fears" and RSS "played on emotions...fear and anger," psychologizing political change as manipulation.
    32. Framing "Islamists helped RSS disseminate views" through terrorism, creating cynical both-sides narrative that denies Hindu security concerns.
    33. Suggesting constitutional questions about UCC or other policies are mere pretexts for Hindu Rashtra rather than legitimate policy debates.
    34. Claiming appointment of "next BJP leader" is decided by RSS rather than democratic party processes.


17. Soft-coded Institutional Delegitimization & Global Risk Framing

    1.  Framing RSS/Hindutva as a **global warning** or a model of democratic decay, even if indirectly (“the world must keep a close eye on their rise”).
    2.  Creating hypothetical, exaggerated scenarios like an **“American RSS”** merging political parties, unions, churches, and militias to evoke fear.
    3.  Describing RSS as part of a global wave of **populism**, **nationalism**, or **authoritarian contagion**, encouraging other nations to treat it as a strategic threat.
    4.  Using selectively positive-sounding terms (e.g., *“world’s most powerful volunteer group,” “boy scouts with attitude”*) in a **sarcastic, delegitimizing, or ominous framing**, implying paramilitarism or infiltration.
    5.  Suggesting that nationalism associated with Hindutva is inherently **volatile**, **dangerous**, or likely to be “turned against minorities.”
    6.  Claiming that people worldwide are “unnerved” or afraid of Hindutva-aligned movements from India, framing them as globally destabilizing forces.
    7.  Advising resistance movements (“offer a better alternative if you don’t want RSS influence”), implying RSS/Hindutva is a **dangerous ideological surge** that must be countered structurally.
    8. Framing global audiences as "unnerved by the rise of nationalism and populist organizations from the Indian subcontinent to the U.S. and beyond," creating international anxiety.
    9. Presenting RSS centenary and longevity ("built to last") as evidence of ominous permanence and structural threat.
    10. Suggesting opposition requires offering "better alternative" to prevent RSS influence, legitimizing the threat narrative.
    11. Claiming Hindu nationalist leaders are architects of "global movement for conservatism," implying transnational ideological coordination.
    12. Advocating that "U.S. law enforcement, politicians, and academic institutions must end partnerships with Hindutva groups," demanding systematic institutional disengagement.
    13. Framing continued institutional partnerships as moral or professional failure requiring correction.

18. Academic Reframing & Normalization of Anti-Hindutva Bias

    1.  Using academic labels like **“far-right movement,” “propaganda,” “global conservative movement”** as universal descriptors of Hindutva, treating these ideological framings as uncontested fact.
    2.  Claiming that Hindutva networks systematically **weaponize misleading data** to push falsehoods in institutions (e.g., U.S. textbook debates), positioning all counter-arguments as disinformation.
    3.  Framing any dissent or correction from Hindutva groups as **maligning scholars**, portraying Hindu advocacy as inherently anti-academic.
    4.  Asserting that Hindu nationalists coordinate or lead a **“global conservative movement”**, implying transnational ideological capture.
    5.  Depicting long-standing RSS leaders’ statements as evidence of a global ideological mission (“World Mission to spread Hindu nationalism”) without nuance.
    6.  Presenting the only legitimate way of “understanding Hindutva” as through a **critical academic lens**, delegitimizing all internal or alternative interpretations.
    7.  Using academic jargon to reframe Hindutva as inherently dangerous, supremacist, or manipulative while maintaining scholarly distance (e.g., “social harms,” “propaganda ecosystem”).
    8. Using terms like "Gujarat pogrom in 2002" without acknowledging legal verdicts or context, establishing guilt as academic consensus.
    9. Describing "dozens of lynchings" by vigilantes "all shown on social media for impacting the Muslim minority even more" as systematic Hindutva campaign.
    10. Claiming "deeper state" operates through vigilante surveillance creating "de facto Hindu Rashtra" with state complicity.
    11. Asserting scholars and observers "are well aware of India's democratic backsliding" as uncontested academic fact.
    12. Describing any attempt at Uniform Civil Code as evidence of Hindu Rashtra project rather than legitimate policy debate.
    13. Framing RSS as systematically creating internal Muslim divisions ("good Muslims" vs. others) as strategy without acknowledging complexity of Muslim communities.
    14. Using academic citations (Jaffrelot, etc.) immediately after inflammatory characterizations to give scholarly veneer to phobic claims.
    15. Describing leaders as "embodying charismatic authoritarian guruship" using academic jargon to pathologize democratic political leadership.
    16. Framing political support as "bhakts/devotees" in academic analysis, treating voters as cult members rather than citizens.


```

# Slurs & Red Flags (Automatic Extraction)
The presence of the following terms will automatically trigger an extraction.

Slurs: RSS goons, saffron terror, sanghi, communalist, chaddi gang, RSS fascist, go mutra wala, gobar bhakt, Cow Belt Bigot, Baman / Brahminical Fascist, IT cell goon, Bindi gang, Manuvadi, pogrom, supremacist, demonize, vigilante, fascist, andh bhaktguruship, charismatic guruship, authoritarian guruship, guru of hate,world-guru, visvaguru, jagatguru, fractal guruship,brand ambassador, brand ambassadors, soft Hindutva,paragon of moral virtue, unparalleled spiritual prowess, moral authority,weaponization of social media, weaponization, intrusive media surveillance,media surveillance,victimised saints, victimised gurus,Hindu Rashtra, Hindu-first constitution, Hindu micro-minority, majoritarianism,transnational network, seeding groups abroad, diaspora influence,cruel optimism, hollow universalism, confined universalism.
Additional Red Flags :"landscape of divisions","deeper state","de facto Hindu Rashtra", "vigilante surveillance""democratic backsliding", "Gujarat pogrom","hatemongers" (when applied to Hindu religious leaders),"militant Hindutva gurus", "hagiographic account", "majoritarianism", "built to last", "seeding groups", "good Muslims", "playing on emotions", "fear and anger", "corrupting Dalits/OBCs","so-called Hinduphobia","innocuous-sounding" / "innocuously-named","far-right commitments","lacked culture".
CONTEXT-DEPENDENT FLAGS (require phrase-level analysis):
- "embodies...guruship" → CHECK: Is it describing intentional strategy vs. inherent pathology?
- "after Modi became" + negative events → CHECK: Is it temporal correlation vs. direct causation claim?
- "self-interest" + "aligning with" → CHECK: Is it standard political analysis vs. malice attribution?
- "seeding groups" → FLAG (conspiratorial language)
- "less deserving of dignity" → FLAG (malice attribution)
- "pushing for Hindu-first constitution, but says doesn't want" → FLAG (goalpost moving)

FACTUAL TEMPORAL CLAIMS (do NOT automatically flag):
- "increases in [violence] after [event]" → Only flag if claims direct orchestration
- "influenced [outcome]" / "affected [policy]" → Only flag if denies all legitimate process

Action: Assign Method: A4: Use of Derogatory Slurs and Score: -10.

Direct Comparisons: Explicitly equating RSS/Hindutva with Nazism, Hitler Youth, Taliban, Proud Boys, SS, Muslim Brotherhood.
Action: Assign Method: A3: Simplistic and Ahistorical Equivalencies and Score: -10.

# CRITICAL CONTEXT REQUIREMENT

Before classifying any statement as phobic, you MUST determine:

1. **Attribution**: Who is making the statement?
   - Is it the author's own view?
   - Is it quoted from someone else (Andersen, critics, opponents)?
   - Is it paraphrased from external sources?

2. **Author's Stance**: What is the author's position on this statement?
   - Is the author ENDORSING this view?
   - Is the author CRITICIZING or CHALLENGING this view?
   - Is the author presenting it as an example of bias/phobia from others?

3. **Framing Indicators** to identify quotes being criticized (NOT phobic):
   - Quotation marks: "..." or '...'
   - Attribution phrases: "Andersen wrote...", "Critics claim...", "He stated...", "According to..."
   - Critical responses: "Such critiques, completely lacking in evidence...", "serious criminal allegations", "oversimplify the complexities..."
   - Distancing language: "so-called", "alleged", "claims that"

  **EXTRACTION RULE**:
  - **EXTRACT**: Only statements that represent the author's OWN phobic views
  - **DO NOT EXTRACT**: Quotes or statements the author is citing FROM OTHERS to criticize or refute
  - **DO NOT EXTRACT**: Examples the author provides of bias/phobia BY OTHERS

  **Example of What NOT to Extract**:Text: Andersen wrote: "No doubt that there are membership elements of RSS who have engaged in lynching." The author follows with: "These are serious criminal allegations."
  ✗ WRONG: Extract "No doubt that there are membership elements of RSS who have engaged in lynching"
  ✓ CORRECT: Do not extract - this is Andersen's quote being presented as problematic by the author

  **Example of What TO Extract**: Text: The RSS is clearly a fascist organization that threatens democracy.
  ✓ CORRECT: Extract this - it's the author's direct claim with no attribution or critical framing



# Extraction Directives (Strict Compliance Required)
1. Granularity First: You MUST operate on a phrase-by-phrase, sentence-by-sentence level so your dont miss any phobic instance.
2. No Clustering: NEVER group multiple distinct phobic sentences into a single entry, even if they are adjacent.
3. Scoring: Each detection MUST be assigned a Score between 1 and 8 ONLY ,DO NOT use negative numbers,DO NOT use 0,DO NOT exceed 8,The scale intentionally stops at 8 to leave room for external document level adjustments


# Strict Output Format (MUST return ONLY JSON, no extra text)
Return exactly one JSON object with this schema:

{
  "document_id": "<string>",
  "summary": {
    "total_detections": 0,
    "strong_phobic": 0,
    "medium_phobic": 0,
    "weak_phobic": 0,
    "notes": "<optional>"
  },"authors": [
      "name 1",
      "name 2",
       Note : the given are from media articles like The wire , India Today, etc so after adding the authors of articles we can add the media house name as well in the same list with the name of author. For example if the article is from The Wire and the author is John Doe then we can add "John Doe - The Wire" in the list of authors.
    ],
  "detections": [
    {
      "id": "<uuid>",
      "sentence": "<the exact phobic sentence/phrase>",
      "score": 3,
      "method_code": "<e.g., A3, A4, B11, etc.>",
      "method_name": "<human-friendly category name>",
      "page": 1,
      "Topic_id":"3.2(Search the provided list of List of Phobic Topics and Examples where the Example Statement is semantically similar or a paraphrase of the detected statement; if a match exists, return only the 'ID' like 3.2 , otherwise, return 'N/A' " )
      "Topic_name":"Framing continued institutional partnerships as moral or professional failure requiring correction.((Search the provided list of List of Phobic Topics and Examples where the Example Statement is semantically similar or a paraphrase of the detected statement; if a match exists, return it,otherwise, return 'N/A' )
      "span_char_start": 1234,
      "span_char_end": 1290,
      "red_flag": true,
      "slur": true,
      "Reasoning": "<one-line literal (non-interpretive) why it matches>"
    }
  ]
}

# Mandatory Scoring Guide

Tier 1: Mild Phobia (Score 1–3)

Nature:
Mockery, stereotyping, casual slurs, weak insinuations.

Examples:
- Internet-style slurs (e.g., "sanghi", "chaddi gang")
- Blaming RSS for unrelated societal events without evidence
- Casual stereotyping
- Non-serious but negative labeling
- Criticizing historical members without substantive evidence

Assign:
1 → Very mild insinuation
2 → Clear mocking tone
3 → Explicit but non-severe phobic framing


Tier 2: Moderate Phobia (Score 4–6)

Nature:
Misinformation, demonization, systemic accusations.

Examples:
- Spreading false historical narratives
- Misrepresenting RSS books/texts deliberately
- Blaming leadership for systemic societal problems without proof
- Claiming institutional corruption without evidence
- Portraying RSS as structurally harmful without substantiation

Assign:
4 → Strong accusation but limited scope
5 → Clear demonization or structured misinformation
6 → Repeated systemic blaming or serious false narrative


Tier 3: Severe Phobia (Score 7–8)

Nature:
Dehumanization, fear-mongering, discrimination, or incitement.

Examples:
- Extreme dehumanizing slurs (e.g., "fascist terrorists", "gomutra")
- Justifying violence or discrimination
- Claiming minorities are in immediate danger due to RSS
- Calls for banning or state action targeting RSS
- Explicit fear amplification narratives

Assign:
7 → Severe demonization or extreme framing
8 → Explicit dehumanization, discrimination, or incitement


# Strict Scoring Rules

- ONLY assign scores between 1 and 8.
- DO NOT use negative numbers.
- DO NOT use +10 / -10 scale anymore.
- Only explicit phobic language should be extracted.
- Non-phobic or neutral statements MUST NOT be included.
- Operate sentence-by-sentence. No clustering.
- Be conservative. Avoid inferential leaps.



Rules:
- Operate sentence-by-sentence. Do NOT cluster multiple sentences into one detection.
- Be conservative; avoid inferential leaps. Focus on explicit, literal phobic statements.
- If none are found, return a valid JSON object with "detections": [] and "summary.total_detections": 0.
- Output ONLY the JSON object. No markdown, no extra prose.
"""


def _init_gemini(api_key: str):
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except ImportError:
        raise ImportError("pip install google-genai")


def _should_skip(article: dict) -> tuple[bool, str]:
    body = (article.get("body") or "").lower()
    for pat in SKIP_FAILURE_PATTERNS:
        if pat in body:
            return True, f"scrape failure: {pat}"
    if len(article.get("body") or "") < 100:
        return True, "body too short"
    return False, ""


def _chunk_text(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = min(start + MAX_CHARS_PER_CHUNK, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - CHARS_OVERLAP
    return chunks


def _safe_parse_json(raw: str) -> dict | None:
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _call_gemini(client, text: str, document_id: str) -> dict | None:
    from google.genai import types
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=f"DOCUMENT ID: {document_id}\n\nTEXT TO ANALYSE:\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.0,
                top_p=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
            ),
        )
        return _safe_parse_json(response.text)
    except Exception as exc:
        log.error("Gemini call failed for %s: %s", document_id, exc)
        return None


def _merge_chunk_results(chunks_results: list, document_id: str, article: dict) -> dict:
    merged_detections = []
    strong = medium = weak = 0

    for cr in chunks_results:
        if not cr:
            continue
        for det in cr.get("detections", []):
            det["id"] = str(uuid.uuid4())
            enrich_detection(det)          # ← taxonomy enrichment here
            merged_detections.append(det)
            score = int(det.get("score", 0))
            if score >= 7:
                strong += 1
            elif score >= 4:
                medium += 1
            else:
                weak += 1

    authors = next((cr["authors"] for cr in chunks_results if cr and cr.get("authors")), [])

    return {
        "document_id":    document_id,
        "title":          article.get("title", ""),
        "url":            article.get("url", ""),
        "site":           article.get("site", ""),
        "published_date": article.get("published_date", ""),
        "body":           article.get("body", ""),
        "search_term":    article.get("search_term", ""),
        "date_range":     article.get("date_range", ""),
        "scrape_status":  article.get("scrape_status", ""),
        "scrape_method":  article.get("scrape_method", ""),
        "authors":        authors,
        "summary": {
            "total_detections": len(merged_detections),
            "strong_phobic":    strong,
            "medium_phobic":    medium,
            "weak_phobic":      weak,
        },
        "detections": merged_detections,
    }


def run(articles: list[dict], config: dict) -> list[dict]:
    """
    Step 2 entry point.
    Returns list of detection dicts, one per article.
    Every detection hit is enriched with taxonomy fields:
      method_name_full, main_category_ids, main_category_names
    """
    import os
    gemini_key = config.get("gemini_key") or os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise ValueError("gemini_key required in config or GEMINI_API_KEY env var")

    client     = _init_gemini(gemini_key)
    detections = []

    log.info("Step 2 — Detecting in %d articles", len(articles))

    for i, article in enumerate(articles, 1):
        doc_id = str(uuid.uuid4())
        log.info("[%d/%d] %s", i, len(articles), article.get("title", "")[:60])

        skip, reason = _should_skip(article)
        if skip:
            log.info("  Skip: %s", reason)
            detections.append({
                "document_id": doc_id,
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "site": article.get("site", ""),
                "published_date": article.get("published_date", ""),
                "body": article.get("body", ""),
                "search_term": article.get("search_term", ""),
                "date_range": article.get("date_range", ""),
                "scrape_status": article.get("scrape_status", ""),
                "scrape_method": article.get("scrape_method", ""),
                "authors": [],
                "status": "skipped",
                "skip_reason": reason,
                "summary": {"total_detections": 0, "strong_phobic": 0, "medium_phobic": 0, "weak_phobic": 0},
                "detections": [],
            })
            continue

        chunks        = _chunk_text(article.get("body", ""))
        chunk_results = []
        log.info("  %d chunk(s)", len(chunks))
        for ci, chunk_text in enumerate(chunks, 1):
            log.info("  chunk %d/%d", ci, len(chunks))
            chunk_results.append(_call_gemini(client, chunk_text, f"{doc_id}_c{ci}"))

        merged         = _merge_chunk_results(chunk_results, doc_id, article)
        merged["status"] = "processed"
        detections.append(merged)
        log.info("  → %d detections (s=%d m=%d w=%d)",
                 merged["summary"]["total_detections"],
                 merged["summary"]["strong_phobic"],
                 merged["summary"]["medium_phobic"],
                 merged["summary"]["weak_phobic"])
        gc.collect()

    total = sum(d["summary"]["total_detections"] for d in detections)
    log.info("Step 2 done — %d total detections", total)
    return detections
