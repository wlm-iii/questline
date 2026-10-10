import { Card, Button, Stamp } from "@dendelion/paper-ui";
import "@dendelion/paper-ui/dist/index.css";

export function QuestCard() {
  return (
    <Card texture="parchment">
      <Stamp variant="warning">Main Quest</Stamp>
      <h3>McWay Falls</h3>
      <p>Nature · Contested waypoint</p>
      <Button variant="primary">View quest</Button>
    </Card>
  );
}
