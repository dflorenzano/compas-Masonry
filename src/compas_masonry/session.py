from compas_dem.elements import Block
from compas_dem.models import BlockModel
from compas_session.lazyload import LazyLoadSession

from .settings import MasonrySettings


class MasonrySession(LazyLoadSession):
    settingsclass = MasonrySettings
    settings: MasonrySettings  # type: ignore

    # set a fail message

    # =============================================================================
    # BlockModel state
    # =============================================================================

    MODEL_LAYERS = [
        "Masonry::Model::Blocks",
        "Masonry::Model::Supports",
        "Masonry::Model::Interactions",
        "Masonry::Model::Contacts",
    ]

    def clear_model(self) -> None:
        """Remove the current BlockModel and everything that depends on it.

        Removes the model's scene objects, clears the model layers, and
        deletes the dependent session artefacts (problem, results), which are
        invalid once the model changes.
        """
        # Rhino/compas_dem imports are local so this module stays importable
        # outside Rhino (headless tests) and cheap to import for TNA commands.
        import compas_rhino.layers
        from compas_dem.elements import Block
        from compas_dem.interactions import FrictionContact
        from compas_model.models import InteractionGraph

        for key in ("blockmodel", "problem", "results"):
            self.delete(key)

        for itemtype in (Block, FrictionContact, InteractionGraph):
            for obj in self.scene.find_all_by_itemtype(itemtype):
                self.scene.remove(obj)

        for layer in self.MODEL_LAYERS:
            compas_rhino.layers.clear_layer(layer)

    def set_model(self, model) -> None:
        """Install `model` as the session BlockModel and draw it.

        Clears the previous model (and dependent problem/results) first.
        This is the shared tail of every model-creating command
        (Model_blocks, Model_import, TNA_blockexports, ...).

        Parameters
        ----------
        model : :class:`compas_dem.models.BlockModel`

        """
        self.clear_model()
        self["blockmodel"] = model
        self.draw_model()

    def draw_model(self) -> None:
        """Draw the session BlockModel: blocks, and (if contacts have been
        computed) the interaction graph and contact interfaces."""
        model = self.get("blockmodel")
        if model is None:
            return

        for block in model.elements():
            node = block.graphnode
            self.scene.add(
                block,  # type: ignore
                name=f"Block_{node}",  # type: ignore
                group=f"Masonry::Model::Blocks::{node}",  # type: ignore
                layer="Masonry::Model::Blocks",  # type: ignore
            )

        if model.graph.number_of_edges() > 0:
            self.scene.add(model.graph, layer="Masonry::Model::Interactions")  # type: ignore
            for contact in model.contacts():
                self.scene.add(contact, layer="Masonry::Model::Contacts")  # type: ignore

        self.redraw()

    def redraw(self) -> None:
        """Redraw the scene and re-tag Block guids.

        Scene.redraw() recreates every drawn Rhino object, not just newly
        added ones, so guids change on every redraw. Route all redraws
        through here so the "element_guid" tag never goes stale.
        """
        self.scene.redraw()
        model = self.get("blockmodel")
        if model is not None:
            self._tag_block_guids(model)

    def _tag_block_guids(self, model) -> None:
        import rhinoscriptsyntax as rs  # type: ignore

        for sceneobj in self.scene.find_all_by_itemtype(Block):
            for guid in sceneobj.guids:
                rs.SetUserText(guid, "element_guid", str(sceneobj.item.guid))

    def guid_element_map(self, model=None) -> dict:
        """Map each Block element's persistent guid (str) to its current graph node.
        Rebuild per-command, not cached — node indices shift as the model changes.

        Parameters
        ----------
        model : :class:`compas_dem.models.BlockModel`, optional
            The model to use. If not provided, the session's current BlockModel is used.

        Returns
        -------
        dict
            A dictionary mapping Rhino GUIDs to Block elements.
        """
        model: BlockModel

        model = model or self.get("blockmodel")
        return {str(model.graph.node_element(n).guid): n for n in model.graph.nodes()}

    def find_node(self, guid, guid_element_map=None):
        """Resolve a Rhino object guid to its current graph node.

        Pass a prebuilt `guid_element_map` when resolving many guids in a loop,
        to avoid rebuilding it per call.
        """
        import rhinoscriptsyntax as rs  # type: ignore

        text = rs.GetUserText(guid, "element_guid")
        if text is None:
            return None
        mapping = guid_element_map if guid_element_map is not None else self.guid_element_map()
        return mapping.get(text)
