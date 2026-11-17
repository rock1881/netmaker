//go:build ce

// Local CE regression coverage for administrator-selected ACL direction.
package logic

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"testing"

	"github.com/google/uuid"
	"github.com/gravitl/netmaker/db"
	"github.com/gravitl/netmaker/models"
	"github.com/gravitl/netmaker/schema"
	"github.com/gravitl/netmaker/scope"
	"github.com/stretchr/testify/require"
)

func TestCEDirectionValidation(t *testing.T) {
	a := models.Acl{RuleType: models.DevicePolicy,
		Src: []models.AclPolicyTag{{ID: models.NodeTagID, Value: "*"}},
		Dst: []models.AclPolicyTag{{ID: models.NodeTagID, Value: "*"}}}
	for _, dir := range []models.AllowedTrafficDirection{models.TrafficDirectionUni, models.TrafficDirectionBi} {
		a.AllowedDirection = dir
		require.NoError(t, IsAclPolicyValid(context.Background(), a))
	}
	for _, dir := range []models.AllowedTrafficDirection{-1, 2} {
		a.AllowedDirection = dir
		require.Error(t, IsAclPolicyValid(context.Background(), a))
	}
}

func TestCEDirectionFirewallSelection(t *testing.T) {
	node := models.Node{CommonNode: models.CommonNode{Network: "n1"}}
	a := models.Acl{NetworkID: "n1", RuleType: models.DevicePolicy, Enabled: true, AllowedDirection: models.TrafficDirectionUni}
	require.True(t, CheckIfAnyPolicyisUniDirectional(node, []models.Acl{a}))
	a.Enabled = false
	require.False(t, CheckIfAnyPolicyisUniDirectional(node, []models.Acl{a}))
	a.Enabled = true
	a.NetworkID = "n2"
	require.False(t, CheckIfAnyPolicyisUniDirectional(node, []models.Acl{a}))
	a.NetworkID = "n1"
	a.AllowedDirection = models.TrafficDirectionBi
	require.False(t, CheckIfAnyPolicyisUniDirectional(node, []models.Acl{a}))
}

func TestCEDirectionPolicyAndPeerUpdates(t *testing.T) {
	ctx := scopedTestContext(t)
	network := schema.Network{Name: "dir-" + uuid.NewString()[:8], TenantID: scope.ID(ctx), AddressRange: "100.90.0.0/24"}
	require.NoError(t, network.Create(ctx))
	t.Cleanup(func() { db.FromContext(ctx).Delete(&network) })
	nodes := make([]models.Node, 3)
	hosts := make([]schema.Host, 3)
	for i := range nodes {
		nodeID := uuid.NewString()
		hosts[i] = schema.Host{ID: uuid.New(), TenantID: scope.ID(ctx), Name: fmt.Sprintf("dir-%d", i), OS: "linux", Version: "v1.7.0", Nodes: []string{nodeID}}
		require.NoError(t, hosts[i].Create(ctx))
		host := &hosts[i]
		t.Cleanup(func() { require.NoError(t, host.Delete(ctx)) })
		n := schema.Node{ID: nodeID, HostID: host.ID.String(), NetworkID: network.ID, TenantID: scope.ID(ctx), Address: fmt.Sprintf("100.90.0.%d/24", i+1), Connected: true, IsGateway: i == 0}
		require.NoError(t, n.Create(ctx))
		t.Cleanup(func() { require.NoError(t, n.Delete(ctx)) })
		var err error
		nodes[i], err = GetNodeByID(nodeID)
		require.NoError(t, err)
	}
	all := models.Acl{ID: network.Name + ".all-nodes", NetworkID: schema.NetworkID(network.Name), RuleType: models.DevicePolicy,
		Default: true, Enabled: false, AllowedDirection: models.TrafficDirectionBi, Proto: models.ALL,
		Src: []models.AclPolicyTag{{ID: models.NodeTagID, Value: "*"}}, Dst: []models.AclPolicyTag{{ID: models.NodeTagID, Value: "*"}}}
	require.NoError(t, UpsertAcl(ctx, all))
	t.Cleanup(func() { require.NoError(t, DeleteAcl(ctx, all)) })
	device := func(i int) []models.AclPolicyTag {
		return []models.AclPolicyTag{{ID: models.NodeID, Value: nodes[i].ID.String()}}
	}
	any := []models.AclPolicyTag{{ID: models.NodeTagID, Value: "*"}}
	gateway := []models.AclPolicyTag{{ID: models.NodeTagID, Value: network.Name + "." + models.GwTagName}}
	cases := []struct {
		name     string
		src, dst []models.AclPolicyTag
		reverse  bool
	}{
		{"device-to-device", device(0), device(1), false},
		{"device-to-all", device(0), any, false},
		{"all-to-device", any, device(1), false},
		{"gateway-group-source", gateway, device(1), false},
		{"gateway-group-destination", device(1), gateway, false},
		{"bidirectional", device(0), device(1), true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			a := models.Acl{ID: uuid.NewString(), NetworkID: schema.NetworkID(network.Name), RuleType: models.DevicePolicy, Enabled: true,
				Src: tc.src, Dst: tc.dst, AllowedDirection: models.TrafficDirectionUni, Proto: models.ALL, ServiceType: models.Any}
			if tc.reverse {
				a.AllowedDirection = models.TrafficDirectionBi
			}
			require.NoError(t, IsAclPolicyValid(ctx, a))
			require.NoError(t, UpsertAcl(ctx, a))
			t.Cleanup(func() { require.NoError(t, DeleteAcl(ctx, a)) })
			MigrateAclPolicies(ctx)
			saved, err := GetAcl(ctx, a.ID)
			require.NoError(t, err)
			require.Equal(t, a.AllowedDirection, saved.AllowedDirection)
			src, dst := 0, 1
			if tc.name == "gateway-group-destination" {
				src, dst = 1, 0
			}
			// WireGuard peering must stay symmetric; INPUT rules govern connection initiation.
			require.True(t, IsPeerAllowed(ctx, nodes[src], nodes[dst], true))
			require.True(t, IsPeerAllowed(ctx, nodes[dst], nodes[src], true))
			updates := make([]models.FwUpdate, 2)
			for j, i := range []int{src, dst} {
				update, err := GetPeerUpdateForHost(ctx, network.Name, &hosts[i], nodes, nil, nil, nil)
				require.NoError(t, err)
				updates[j] = update.FwUpdate
				if !tc.reverse {
					require.False(t, update.FwUpdate.AllowAll, "one-way policy must not leave the firewall in accept-all mode")
					require.Empty(t, update.FwUpdate.AllowedNetworks, "network-wide ACCEPT must not bypass direction")
				}
			}
			if !tc.reverse {
				require.True(t, ceRulesAllow(updates[1].AclRules, nodes[src].Address.IP, nodes[dst].Address.IP), "destination must accept the source")
				require.False(t, ceRulesAllow(updates[0].AclRules, nodes[dst].Address.IP, nodes[src].Address.IP), "source must not accept reverse NEW traffic")
			}
			// Optional export feeds the actual Netclient firewall integration harness.
			if tc.name == "device-to-device" && os.Getenv("ACL_DIRECTION_FIXTURE_DIR") != "" {
				for i, u := range updates {
					b, err := json.MarshalIndent(u, "", "  ")
					require.NoError(t, err)
					require.NoError(t, os.WriteFile(filepath.Join(os.Getenv("ACL_DIRECTION_FIXTURE_DIR"), fmt.Sprintf("%s-%d.json", tc.name, i)), b, 0600))
				}
			}
		})
	}
	t.Run("static-client-via-gateway", func(t *testing.T) {
		ec := models.ExtClient{ClientID: "direction-macos", Network: network.Name, Address: "100.90.0.250", IngressGatewayID: nodes[0].ID.String(), Enabled: true}
		require.NoError(t, SaveExtClient(ctx, &ec))
		key, err := GetRecordKey(ec.ClientID, ec.Network)
		require.NoError(t, err)
		t.Cleanup(func() { require.NoError(t, (&schema.ExtClientRecord{Key: key}).Delete(ctx)) })
		a := models.Acl{ID: uuid.NewString(), NetworkID: schema.NetworkID(network.Name), RuleType: models.DevicePolicy, Enabled: true,
			Src: []models.AclPolicyTag{{ID: models.NodeID, Value: ec.ClientID}}, Dst: any,
			AllowedDirection: models.TrafficDirectionUni, Proto: models.ALL, ServiceType: models.Any}
		require.NoError(t, IsAclPolicyValid(ctx, a))
		require.NoError(t, UpsertAcl(ctx, a))
		t.Cleanup(func() { require.NoError(t, DeleteAcl(ctx, a)) })
		require.False(t, IsNodeAllowedToCommunicateWithAllRsrcs(ctx, models.ConvertToStaticNode(ec)))
		require.True(t, ceRulesAllow(GetAclRulesForNode(ctx, &nodes[1]), net.ParseIP(ec.Address), nodes[1].Address.IP))
		rules := GetFwRulesOnIngressGateway(ctx, nodes[0])
		forward, reverse := false, false
		for _, r := range rules {
			forward = forward || (r.Allow && r.SrcIP.Contains(net.ParseIP(ec.Address)) && r.DstIP.Contains(nodes[1].Address.IP))
			reverse = reverse || (r.Allow && r.SrcIP.Contains(nodes[1].Address.IP) && r.DstIP.Contains(net.ParseIP(ec.Address)))
		}
		require.True(t, forward, "gateway must forward static client to destination")
		require.False(t, reverse, "gateway must reject reverse NEW traffic to static client")
	})

}

func ceRulesAllow(rules map[string]models.AclRule, src, dst net.IP) bool {
	for _, r := range rules {
		srcMatch, dstMatch := false, len(r.Dst) == 0
		for _, ip := range r.IPList {
			srcMatch = srcMatch || ip.Contains(src)
		}
		for _, ip := range r.Dst {
			dstMatch = dstMatch || ip.Contains(dst)
		}
		if r.Allowed && srcMatch && dstMatch {
			return true
		}
	}
	return false
}
