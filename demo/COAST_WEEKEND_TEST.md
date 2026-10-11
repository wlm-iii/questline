# Coast weekend: what to test

One trip, three people, two days. Use this instead of the San Francisco demo when you want to know whether real trip data is working. The demo at the site root is still local sample stops (Tartine, Dolores, made-up prices). It does not talk to the API.

Trip file: [coast-weekend.json](coast-weekend.json).

| | |
| --- | --- |
| Trip | Coast weekend |
| Who | Maya organizes. Sam and Jordan join. |
| When | Sat 17 Oct 2026 through Sun 18 Oct 2026 |
| Where | San Jose, CA → Big Sur, CA |
| Time zone | America/Los_Angeles |

Places the chat is supposed to produce:

| Place | How it gets on the trip | What the chat says |
| --- | --- | --- |
| McWay Falls | Named in the paste | Maya wants it. Sam wants to skip it. Jordan is fine either way. |
| Big Sur Bakery | Named in the paste, and added again by search | Breakfast. Everyone is in or fine with it. |
| Bixby Bridge | Named in the paste | Photo stop on the drive. |
| Pfeiffer Beach | Named in the paste | Optional detour. |
| Nepenthe | Named in the paste | Expensive dinner, easy to drop. |
| Mystery Cafe | Named in the paste | Sam heard of it. Nobody has been. This one should fail to resolve. |

## Load it

Start the API first (`docker compose up --build` from the repo root, or your usual backend). Then, from `backend/`:

```sh
uv run python scripts/seed_demo.py ../demo/coast-weekend.json --skip-build
```

The script prints a `/t/<trip id>` link and a member token for Maya, Sam, and Jordan. Keep those. Do not paste tokens into chat or commit them.

`--skip-build` is intentional. With Gemini extraction turned on, Build currently answers that planning is not available. The seed script records that and still leaves the trip in place.

Which places appear depends on the backend provider:

- **Fake maps and fake extraction** (the default): only McWay Falls and Big Sur Bakery resolve. Mystery Cafe is recognized and then listed as unresolved, because fake maps has no such place. Bixby Bridge, Pfeiffer Beach, and Nepenthe are not extracted at all.
- **Google Places plus Gemini extraction**: all six names should be attempted. Mystery Cafe should land under "Couldn't place" unless Google actually resolves that name. The other five should become waypoints. Prices and hours stay unknown. Show "Price unknown", never $0 or "Free".

## What you can check today

The website does not create, join, or show this trip yet. Check the API, not the San Francisco page.

Open `http://localhost:8000/docs`. You do not need the service token for these. Use `X-Member-Token` with Maya's token from the script output.

Pass if all of these are true:

1. `GET /api/v1/trips/{id}` returns the trip name "Coast weekend", origin San Jose, destination Big Sur, dates 2026-10-17 and 2026-10-18, and three members: Maya, Sam, Jordan.
2. The same request with `?revision=<that revision>` returns `{ "unchanged": true, revision }` and does not repeat the whole trip.
3. Places include McWay Falls and Big Sur Bakery, each with coordinates, a category, and null cost fields. There is one Big Sur Bakery even though the chat and the search both mention it.
4. McWay Falls is contested: at least one `in` vote and one `out` vote. Bakery votes are `in` or `ok` only, so it is not contested.
5. Messages are the ten lines from the file. Importing the file a second time does not duplicate them.
6. `POST /api/v1/trips/{id}/plan-generations` with `budget_preset: "treat"` and an `Idempotency-Key` either returns 503 "not available", or returns a plan whose stop list is empty. Waypoints and votes are still there afterwards.
7. `POST /api/v1/trips/{id}/tasks` with Maya's token, the McWay place id, and text `Check the parking turnout` creates a task. `POST /api/v1/places/{place id}/checkins` then `DELETE` that same path adds and removes one shared check-in.

Fail if a place shows up with no coordinates, if Mystery Cafe becomes a pin under fake maps, if a missing price is 0, or if a second seed of the same chat doubles the messages.

## What the page should do once create, join, and the live trip are connected

Use a normal window for Maya and a private window for Sam. Leave the San Francisco demo at `/demo` and do not compare the two.

1. **Create.** On `/`, enter the trip name, San Jose, CA, Big Sur, CA, 2026-10-17, 2026-10-18, and Maya. Time zone fills itself. Travel mode and constraints, if shown, say they stay on this device. Submit. The address becomes `/t/<id>`. Refresh and you are still Maya.
2. **Join.** In the private window, open that same URL, enter Sam, and submit. Within about 3 seconds Maya's window lists Sam. The page says anyone with the link can join.
3. **Share.** Copy link produces that `/t/<id>` URL, not a note that the demo does not sync.
4. **Map.** San Jose and Big Sur are separate start and end markers. Nothing draws a driving line between them. With no browser map key, the page says the map needs a key instead of showing the illustrated San Francisco map.
5. **Import.** Paste the `chat` text from `coast-weekend.json`. The page shows a message count, then a running import, then the places from the table above. McWay's card quotes Maya and Sam. Mystery Cafe, if unresolved, appears under "Couldn't place" and is not a pin.
6. **Search.** Add `Big Sur Bakery` from the place box. If import already added it, the board still has one bakery.
7. **Order on this device.** Reorder or mark a place as a side trip. The page says this is saved on this device only. Sam's window does not change. A real plan, when one exists, replaces that local order.
8. **Quest log.** Add the parking task on McWay. It shows "Anyone in the crew" unless you assign Sam or Jordan. Quest complete stays off until a plan is accepted.
9. **Build.** Pick Treat and press Build. The Questline tab says planning is not available yet, or that the planner returned no stops. The map and the other tabs still work. Accept stays unavailable until a plan exists. If you accept an empty plan, quest complete turns on, and a failed rebuild does not wipe the places.

Still not testable after that, because the backend or the vote source is not there yet: website vote buttons, the S–C tier list, a real driving route, times, dollar totals, editing the trip name or dates, deleting a place, shared notes, and an owner read out of the chat.
